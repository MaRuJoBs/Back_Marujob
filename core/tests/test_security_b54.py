"""B54 gap coverage and explicit characterization of unresolved findings.

Finding tests assert current behavior, not security approval. Update them with
the approved fixes; do not treat their success as remediation.
"""

# ruff: noqa: PT009, PT027
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from core.models import User
from core.tests.test_profiles_portfolios import MediaAPITestCase


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

    def test_finding_01_password_change_keeps_preexisting_tokens_usable(self):
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
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)
        self.client.credentials()
        response = self.client.post('/api/token/refresh/', {'refresh': str(refresh)})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 200)


@override_settings(GOOGLE_CLIENT_ID='b54-offline-client', MAX_IMAGE_UPLOAD_BYTES=8)
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

    def test_finding_02_google_photo_bypasses_content_and_size_validation(self):
        harmless_content = b'Harmless audit text, deliberately not an image.'
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.views.user.requests.get', return_value=Mock(status_code=200, content=harmless_content)),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.claims['email'])
        with user.profile_image.open('rb') as stored:
            self.assertEqual(stored.read(), harmless_content)
        self.assertGreater(len(harmless_content), 8)

    def test_finding_02_google_storage_error_returns_500_and_leaves_account(self):
        self.client.raise_request_exception = False
        with (
            patch('core.views.user.id_token.verify_oauth2_token', return_value=self.claims),
            patch('core.views.user.requests.get', return_value=Mock(status_code=200, content=b'harmless')),
            patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('synthetic-storage-error')),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 500)
        self.assertTrue(User.objects.filter(email=self.claims['email']).exists())
        self.assertNotIn(b'synthetic-storage-error', response.content)
