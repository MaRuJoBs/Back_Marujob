"""B54 regressions: enforce password-state revocation and safe optional photos."""

# ruff: noqa: PT009, PT027
from datetime import timedelta
from unittest.mock import MagicMock, patch

from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth.models import Group
from django.test import override_settings
from requests.exceptions import Timeout
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from core.models import User
from core.tests.test_profiles_portfolios import MediaAPITestCase, image_upload


class TokenBoundaryAuditTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.worker = User.objects.create_user('b54-worker@example.invalid', 'Original-B54-8273!')
        cls.worker.groups.add(Group.objects.get(name='Usuário'))

    def test_missing_invalid_expired_and_refresh_credentials_on_protected_routes(self):
        expired = AccessToken.for_user(self.worker)
        expired.set_exp(lifetime=timedelta(seconds=-60))
        routes = [
            '/api/usuarios/me/',
            '/api/usuarios/',
            '/api/portfolios/',
            '/api/freelances/',
            '/api/favoritos/',
            '/api/candidaturas/',
            '/api/notificacoes/',
            '/api/empresas/me/',
            '/api/freelancers/',
        ]
        for token in [None, 'invalid', str(expired), str(RefreshToken.for_user(self.worker))]:
            self.client.credentials(**({'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}))
            for route in routes:
                with self.subTest(route=route, credential_kind='missing' if token is None else 'rejected'):
                    response = self.client.get(route)
                    self.assertEqual(response.status_code, 401)
                    self.assertNotIn('Traceback', response.content.decode())

    def test_inactive_account_rejects_previously_issued_access_and_refresh(self):
        refresh = RefreshToken.for_user(self.worker)
        self.worker.is_active = False
        self.worker.save(update_fields=['is_active'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code, 401)

    def test_password_change_revokes_preexisting_access_and_refresh(self):
        refresh = RefreshToken.for_user(self.worker)
        access = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.post(
            '/api/auth/trocar-senha/',
            {
                'senha_atual': 'Original-B54-8273!',
                'nova_senha': 'Replacement-B54-9217!',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
        self.client.credentials()
        response = self.client.post('/api/token/refresh/', {'refresh': str(refresh)})
        self.assertEqual(response.status_code, 401)
        response = self.client.post(
            '/api/token/',
            {
                'email': self.worker.email,
                'password': 'Replacement-B54-9217!',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)

    def test_current_refresh_keeps_existing_response_contract(self):
        refresh = RefreshToken.for_user(self.worker)
        response = self.client.post('/api/token/refresh/', {'refresh': str(refresh)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'access'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)

    def test_legacy_tokens_without_password_claim_require_login(self):
        refresh = RefreshToken.for_user(self.worker)
        del refresh['hash_password']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code, 401)

    def test_deleted_user_refresh_is_rejected_without_server_error(self):
        refresh = RefreshToken.for_user(self.worker)
        self.worker.delete()
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code, 401)

    def test_google_initial_password_revokes_old_tokens_and_allows_new_login(self):
        self.worker.google_id = 'b54-google-existing-sub'
        self.worker.set_unusable_password()
        self.worker.save()
        claims = {
            'email': self.worker.email,
            'email_verified': True,
            'sub': self.worker.google_id,
            'aud': 'b54-offline-client',
        }
        with (
            override_settings(GOOGLE_CLIENT_ID='b54-offline-client'),
            patch('core.views.user.id_token.verify_oauth2_token', return_value=claims),
        ):
            before = self.client.post('/api/auth/google/', {'credential': 'synthetic'}, format='json')
            self.assertEqual(before.status_code, 200)
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {before.data["access"]}')
            self.assertEqual(
                self.client.post(
                    '/api/auth/definir-senha/',
                    {
                        'senha': 'Initial-B54-9527!',
                    },
                ).status_code,
                200,
            )
            self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
            self.client.credentials()
            self.assertEqual(
                self.client.post(
                    '/api/token/refresh/',
                    {
                        'refresh': before.data['refresh'],
                    },
                ).status_code,
                401,
            )
            after = self.client.post('/api/auth/google/', {'credential': 'synthetic'}, format='json')
        self.assertEqual(after.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {after.data["access"]}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)


@override_settings(GOOGLE_CLIENT_ID='b54-offline-client', MAX_IMAGE_UPLOAD_BYTES=4096)
class GooglePhotoAuditTests(MediaAPITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=None)
        self.claims = {
            'email': 'b54-google@example.invalid',
            'email_verified': True,
            'name': 'Synthetic B54',
            'sub': 'b54-synthetic-google-sub',
            'aud': 'b54-offline-client',
            'picture': 'https://photo.example.invalid/synthetic',
        }

    def register(self):
        return self.client.post(
            '/api/auth/google/',
            {
                'credential': 'synthetic-verified-by-mock',
                'cadastro': True,
                'tipo': 'usuario',
            },
            format='json',
        )

    def download(self, content=b'', status=200):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.iter_content.return_value = iter([content])
        return response

    def test_invalid_content_is_omitted_without_breaking_registration(self):
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=self.download(b'Harmless non-image text')),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.claims['email'])
        self.assertFalse(user.profile_image)

    def test_storage_error_keeps_verified_account_and_returns_tokens(self):
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=self.download(image_upload().read())),
            patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('synthetic-storage-error')),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertFalse(User.objects.get(email=self.claims['email']).profile_image)
        self.assertNotIn(b'synthetic-storage-error', response.content)

    def test_valid_images_use_detected_format_and_normal_storage(self):
        for image_format, extension in [('PNG', 'png'), ('JPEG', 'jpg'), ('WEBP', 'webp')]:
            with self.subTest(image_format=image_format):
                self.claims['email'] = f'b54-{extension}@example.invalid'
                self.claims['sub'] = f'b54-{extension}-sub'
                content = image_upload(name=f'image.{extension}', image_format=image_format).read()
                download = self.download(content)
                with (
                    patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
                    patch('core.google_photo.requests.get', return_value=download) as get,
                ):
                    response = self.register()
                self.assertEqual(response.status_code, 200)
                get.assert_called_once_with(self.claims['picture'], timeout=10, stream=True, allow_redirects=False)
                user = User.objects.get(email=self.claims['email'])
                self.assertTrue(user.profile_image.name.endswith('.' + extension))
                with user.profile_image.open('rb') as stored:
                    self.assertEqual(stored.read(), content)
                download.__exit__.assert_called_once()

    @override_settings(MAX_IMAGE_UPLOAD_BYTES=8)
    def test_oversize_stream_stops_before_reading_remaining_chunks(self):
        download = self.download()
        chunks = iter([b'12345678', b'9', b'not-read'])
        download.iter_content.return_value = chunks
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=download),
            patch('django.core.files.storage.FileSystemStorage._save') as save,
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(next(chunks), b'not-read')
        save.assert_not_called()
        download.__exit__.assert_called_once()

    def test_network_failure_is_optional_and_does_not_leak_exception(self):
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', side_effect=Timeout('synthetic-private-detail')),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'synthetic-private-detail', response.content)
        self.assertFalse(User.objects.get(email=self.claims['email']).profile_image)

    def test_redirect_response_is_not_followed_or_stored(self):
        download = self.download(status=302)
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=download),
        ):
            self.assertEqual(self.register().status_code, 200)
        download.iter_content.assert_not_called()
        self.assertFalse(User.objects.get(email=self.claims['email']).profile_image)

    def test_unverified_credential_never_triggers_download(self):
        with (
            patch('core.views.user.id_token.verify_oauth2_token', side_effect=ValueError('invalid')),
            patch('core.google_photo.requests.get') as get,
        ):
            self.assertEqual(self.register().status_code, 400)
        get.assert_not_called()

    def test_existing_photo_is_preserved_on_google_login(self):
        user = User.objects.create_user(self.claims['email'], google_id=self.claims['sub'])
        user.profile_image = 'users/already-stored.png'
        user.save()
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get') as get,
        ):
            response = self.client.post('/api/auth/google/', {'credential': 'synthetic'}, format='json')
        self.assertEqual(response.status_code, 200)
        get.assert_not_called()
        user.refresh_from_db()
        self.assertEqual(user.profile_image.name, 'users/already-stored.png')

    def test_non_https_and_credentialed_urls_are_not_requested(self):
        for index, url in enumerate([
            'http://photo.example.invalid/a',
            'file:///synthetic',
            'https://user:pass@photo.example.invalid/a',
        ]):
            self.claims.update(email=f'b54-url-{index}@example.invalid', sub=f'b54-url-{index}', picture=url)
            with (
                patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
                patch('core.google_photo.requests.get') as get,
            ):
                self.assertEqual(self.register().status_code, 200)
            get.assert_not_called()

    def test_unsupported_format_and_excessive_dimensions_are_not_stored(self):
        cases = [(image_upload(name='image.gif', image_format='GIF').read(), None), (image_upload().read(), 1)]
        for index, (content, pixel_limit) in enumerate(cases):
            self.claims.update(email=f'b54-image-{index}@example.invalid', sub=f'b54-image-{index}')
            with (
                patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
                patch('core.google_photo.requests.get', return_value=self.download(content)),
                patch('PIL.Image.MAX_IMAGE_PIXELS', pixel_limit),
                patch('django.core.files.storage.FileSystemStorage._save') as save,
            ):
                self.assertEqual(self.register().status_code, 200)
            save.assert_not_called()

    def test_stream_timeout_is_handled_and_response_is_closed(self):
        download = self.download()
        download.iter_content.side_effect = Timeout('synthetic-private-detail')
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=download),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        download.__exit__.assert_called_once()
        self.assertNotIn(b'synthetic-private-detail', response.content)

    def test_cloudinary_failure_does_not_block_existing_google_login(self):
        user = User.objects.create_user(self.claims['email'], google_id=self.claims['sub'])
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.google_photo.requests.get', return_value=self.download(image_upload().read())),
            patch(
                'django.core.files.storage.FileSystemStorage._save', side_effect=CloudinaryError('synthetic-private')
            ),
        ):
            response = self.client.post('/api/auth/google/', {'credential': 'synthetic'}, format='json')
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.profile_image)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)
