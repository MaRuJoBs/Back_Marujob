# Django's unittest assertions keep API response diagnostics consistent with FEAT-39.
# ruff: noqa: PT009, PT027
import json
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cloudinary.exceptions import Error as CloudinaryError
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from core.models import Portfolio, User


def image_upload(name='test.png', image_format='PNG', content_type='image/png'):
    with BytesIO() as buffer:
        Image.new('RGB', (8, 8), 'blue').save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class MediaAPITestCase(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = TemporaryDirectory(prefix='.feat40-media-', dir=Path(__file__).resolve().parents[2])
        cls.addClassCleanup(cls.media.cleanup)
        cls.storage_settings = override_settings(
            MEDIA_ROOT=cls.media.name,
            STORAGES={
                **settings.STORAGES,
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            },
        )
        cls.storage_settings.enable()
        cls.addClassCleanup(cls.storage_settings.disable)

    @classmethod
    def setUpTestData(cls):
        cls.worker = User.objects.create_user('profile-worker@example.com', 'test-password')
        cls.other = User.objects.create_user('profile-other@example.com', 'test-password')
        cls.company = User.objects.create_user('profile-company@example.com', 'test-password')
        group = Group.objects.get(name='Usuário')
        cls.worker.groups.add(group)
        cls.other.groups.add(group)
        cls.company.groups.add(Group.objects.get(name='Empresa'))

    def setUp(self):
        self.client.force_authenticate(self.worker)


class ProfileTests(MediaAPITestCase):
    url = '/api/usuarios/me/'

    def test_get_profile_and_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.worker.pk)
        self.assertEqual(response.data['tipo'], 'usuario')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.patch(self.url, {}).status_code, 401)

    def test_patch_persists_fields_and_keeps_omitted_values(self):
        data = {
            'name': 'Freelancer',
            'profissao': 'Designer',
            'telefone': '+55 (47) 99999-0000',
            'sobre': 'Trabalho profissional',
            'localizacao': 'Joinville, SC',
            'habilidades': ['Design', 'Python'],
            'aviso_perfil_dispensado': True,
        }
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['perfil_configurado'])
        self.assertEqual(self.client.patch(self.url, {'name': 'Novo nome'}, format='json').status_code, 200)
        self.worker.refresh_from_db()
        data['name'] = 'Novo nome'
        queried = self.client.get(self.url).data
        for field, value in data.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(self.worker, field), value)
                self.assertEqual(queried[field], value)

    def test_profile_completion_requires_existing_fields(self):
        response = self.client.patch(self.url, {'name': 'Only name', 'perfil_configurado': True}, format='json')
        self.assertFalse(response.data['perfil_configurado'])
        self.client.patch(
            self.url,
            {
                'profissao': 'Dev',
                'localizacao': 'Cidade, UF',
                'sobre': 'Sobre',
                'telefone': '123',
            },
            format='json',
        )
        self.assertTrue(self.client.get(self.url).data['perfil_configurado'])
        self.client.patch(self.url, {'sobre': '   '}, format='json')
        self.assertFalse(self.client.get(self.url).data['perfil_configurado'])

    def test_protected_fields_cannot_be_changed(self):
        response = self.client.patch(
            self.url,
            {
                'id': self.other.pk,
                'email': 'hacked@example.com',
                'groups': [],
                'tipo': 'empresa',
                'is_staff': True,
                'is_superuser': True,
                'is_active': False,
                'user_permissions': [1],
                'google_id': 'attacker',
                'password': 'hacked',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.email, 'profile-worker@example.com')
        self.assertTrue(self.worker.is_active)
        self.assertFalse(self.worker.is_staff)
        self.assertFalse(self.worker.is_superuser)
        self.assertIsNone(self.worker.google_id)
        self.assertTrue(self.worker.check_password('test-password'))
        self.assertEqual(response.data['tipo'], 'usuario')
        self.assertFalse(self.worker.user_permissions.exists())

    def test_text_limits(self):
        for field, length in [('name', 255), ('profissao', 255), ('localizacao', 255), ('telefone', 30)]:
            with self.subTest(field=field):
                response = self.client.patch(self.url, {field: 'x' * (length + 1)}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_skills_json_and_multipart_remain_lists(self):
        for encoding, skills in [('json', ['Python', 'Django']), ('multipart', '["Design"," API ","Design"]')]:
            response = self.client.patch(self.url, {'habilidades': skills}, format=encoding)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIsInstance(response.data['habilidades'], list)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.habilidades, ['Design', 'API'])
        self.client.patch(self.url, {'name': 'Preserved'}, format='json')
        self.assertEqual(self.client.get(self.url).data['habilidades'], ['Design', 'API'])
        self.client.patch(self.url, {'habilidades': '[]'}, format='multipart')
        self.assertEqual(self.client.get(self.url).data['habilidades'], [])

    def test_invalid_skills(self):
        for value in [{}, '[]', [1], [True], [[]], [''], None, ['a'] * 51, ['x' * 101]]:
            with self.subTest(value=value):
                self.assertEqual(self.client.patch(self.url, {'habilidades': value}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'habilidades': '[broken'}, format='multipart').status_code, 400)

    def test_valid_gps_and_manual_clearing(self):
        data = {
            'localizacao': 'Joinville, SC',
            'latitude': -26.3,
            'longitude': -48.8,
            'geolocation_accuracy': 12.5,
            'geolocation_timestamp': timezone.now().isoformat(),
        }
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.latitude, -26.3)
        self.assertEqual(self.worker.longitude, -48.8)
        self.assertEqual(self.worker.geolocation_accuracy, 12.5)
        self.assertIsNotNone(self.worker.geolocation_timestamp)
        response = self.client.patch(
            self.url,
            {
                'localizacao': 'Outra cidade, SC',
                'latitude': None,
                'longitude': None,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.worker.refresh_from_db()
        for field in ['latitude', 'longitude', 'geolocation_accuracy', 'geolocation_timestamp']:
            self.assertIsNone(getattr(self.worker, field))

    def test_gps_errors(self):
        for data in [
            {'latitude': 1},
            {'longitude': 1},
            {'latitude': 91, 'longitude': 1},
            {'latitude': 1, 'longitude': -181},
            {'latitude': 'NaN', 'longitude': 1},
            {'latitude': 1, 'longitude': 1, 'geolocation_accuracy': -1},
            {'latitude': 1, 'longitude': 1, 'geolocation_accuracy': 'Infinity'},
            {'geolocation_accuracy': 10},
            {'geolocation_timestamp': timezone.now().isoformat()},
            {'latitude': 1, 'longitude': 1, 'geolocation_timestamp': 'not-a-date'},
            {'latitude': 1, 'longitude': 1, 'geolocation_timestamp': (timezone.now() + timedelta(days=1)).isoformat()},
        ]:
            with self.subTest(data=data):
                self.assertEqual(self.client.patch(self.url, data, format='json').status_code, 400)

    def test_private_location_is_not_available_to_other_users(self):
        self.worker.latitude = -26.3
        self.worker.longitude = -48.8
        self.worker.save()
        self.client.force_authenticate(self.company)
        response = self.client.get(f'/api/usuarios/{self.worker.pk}/')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('latitude', response.data)

    def test_unrelated_patch_preserves_legacy_metadata(self):
        self.worker.geolocation_accuracy = -1
        self.worker.save()
        response = self.client.patch(self.url, {'name': 'Changed'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.geolocation_accuracy, -1)
        self.assertEqual(self.client.patch(self.url, {'geolocation_accuracy': -1}, format='json').status_code, 400)

    def test_profile_upload_with_text_and_skills(self):
        response = self.client.patch(
            self.url,
            {
                'name': 'Upload',
                'profissao': 'Dev',
                'habilidades': '["Python"]',
                'profile_image': image_upload(),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.worker.refresh_from_db()
        self.assertTrue(Path(self.media.name, self.worker.profile_image.name).is_file())
        self.assertEqual(response.data['profile_image'], f'http://testserver/media/{self.worker.profile_image.name}')
        self.assertEqual(self.client.get(self.url).data['profile_image'], response.data['profile_image'])
        self.assertEqual(response.data['habilidades'], ['Python'])
        self.assertEqual(response.data['name'], 'Upload')

    def test_profile_image_omission_replacement_and_removal(self):
        self.client.patch(self.url, {'profile_image': image_upload()}, format='multipart')
        self.worker.refresh_from_db()
        first = self.worker.profile_image.name
        self.client.patch(self.url, {'name': 'No image change'}, format='json')
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.profile_image.name, first)
        response = self.client.patch(self.url, {'profile_image': image_upload()}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.worker.refresh_from_db()
        self.assertNotEqual(self.worker.profile_image.name, first)
        self.assertTrue(Path(self.media.name, first).exists())
        current = self.worker.profile_image.name
        self.assertEqual(self.client.patch(self.url, {'profile_image': None}, format='json').status_code, 200)
        self.assertIsNone(self.client.get(self.url).data['profile_image'])
        self.assertTrue(Path(self.media.name, current).exists())

    def test_profile_image_content_validation_and_limit(self):
        for upload in [
            SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'),
            image_upload('animation.gif', 'GIF', 'image/gif'),
            SimpleUploadedFile('broken.png', b'\x89PNG\r\n\x1a\n', content_type='image/png'),
        ]:
            with self.subTest(name=upload.name):
                self.assertEqual(
                    self.client.patch(self.url, {'profile_image': upload}, format='multipart').status_code, 400
                )
        with override_settings(MAX_IMAGE_UPLOAD_BYTES=10):
            response = self.client.patch(self.url, {'profile_image': image_upload()}, format='multipart')
            self.assertEqual(response.status_code, 400)
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 1):
            response = self.client.patch(self.url, {'profile_image': image_upload()}, format='multipart')
            self.assertEqual(response.status_code, 400)
        # A forged client MIME type cannot replace actual image inspection.
        response = self.client.patch(
            self.url,
            {
                'profile_image': image_upload(content_type='text/plain'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)

    def test_allowed_image_formats_and_multipart_coordinate_clearing(self):
        for name, image_format in [('valid.jpg', 'JPEG'), ('valid.png', 'PNG'), ('valid.webp', 'WEBP')]:
            with self.subTest(image_format=image_format):
                response = self.client.patch(
                    self.url,
                    {
                        'profile_image': image_upload(name, image_format),
                    },
                    format='multipart',
                )
                self.assertEqual(response.status_code, 200, response.data)
        self.client.patch(self.url, {'latitude': 1, 'longitude': 2, 'geolocation_accuracy': 10}, format='json')
        response = self.client.patch(
            self.url,
            {
                'latitude': '',
                'longitude': '',
                'localizacao': 'Cidade manual',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['latitude'])
        self.assertIsNone(response.data['longitude'])
        self.assertIsNone(response.data['geolocation_accuracy'])

    def test_registration_image_uses_same_validation(self):
        self.client.force_authenticate(None)
        data = {
            'email': 'registration-image@example.com',
            'password': 'Safe-Registration-40292!',
            'tipo': 'usuario',
            'profile_image': image_upload(),
        }
        response = self.client.post('/api/registro/', data, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.get(email=data['email']).profile_image)
        data['email'] = 'invalid-registration@example.com'
        data['profile_image'] = SimpleUploadedFile('fake.png', b'invalid', content_type='image/png')
        self.assertEqual(self.client.post('/api/registro/', data, format='multipart').status_code, 400)
        self.assertFalse(User.objects.filter(email=data['email']).exists())

    def test_profile_storage_failure_is_safe_and_rolls_back(self):
        storage = User._meta.get_field('profile_image').storage
        with patch.object(storage, '_save', side_effect=OSError('private path and credentials')):
            response = self.client.patch(
                self.url,
                {
                    'name': 'Should not persist',
                    'profile_image': image_upload(),
                },
                format='multipart',
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private path', str(response.data))
        self.worker.refresh_from_db()
        self.assertIsNone(self.worker.name)
        self.assertFalse(self.worker.profile_image)

    def test_cloudinary_upload_and_url_are_preserved_without_network(self):
        remote = MediaCloudinaryStorage()
        url = 'https://res.cloudinary.com/test-only/image/upload/users/test-image'
        with (
            patch.object(User._meta.get_field('profile_image'), 'storage', remote),
            patch.object(remote, '_upload', return_value={'public_id': 'users/test-image'}) as upload,
            patch.object(remote, 'url', return_value=url),
        ):
            response = self.client.patch(self.url, {'profile_image': image_upload()}, format='multipart')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['profile_image'], url)
            upload.assert_called_once()


class PortfolioTests(MediaAPITestCase):
    url = '/api/portfolios/'

    def project_data(self, **extra):
        return {
            'titulo': 'Projeto',
            'categoria': 'Web',
            'descricao': 'Descrição profissional',
            'tags': ['Django', 'Python'],
            'link': 'https://example.com/project',
            **extra,
        }

    def create_project(self, **extra):
        return Portfolio.objects.create(usuario=self.worker, **self.project_data(**extra))

    def detail(self, project):
        return f'{self.url}{project.pk}/'

    def test_create_without_image_and_automatic_owner(self):
        response = self.client.post(self.url, self.project_data(usuario=self.other.pk), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        project = Portfolio.objects.get(pk=response.data['id'])
        self.assertEqual(project.usuario, self.worker)
        self.assertFalse(project.imagem)
        self.assertIsNone(response.data['imagem'])
        self.assertEqual(response.data['tags'], ['Django', 'Python'])
        self.assertNotIn('usuario', response.data)

    def test_list_detail_and_pagination(self):
        projects = [self.create_project(titulo=f'Projeto {index}') for index in range(11)]
        Portfolio.objects.create(usuario=self.other, **self.project_data(titulo='Hidden'))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        second = self.client.get(self.url, {'page': 2})
        self.assertEqual([item['id'] for item in second.data['results']], [projects[-1].pk])
        response = self.client.get(self.detail(projects[0]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['titulo'], projects[0].titulo)

    def test_put_updates_project_without_changing_owner(self):
        project = self.create_project()
        response = self.client.put(
            self.detail(project),
            self.project_data(
                titulo='Updated',
                tags=['API'],
                usuario=self.other.pk,
            ),
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        project.refresh_from_db()
        self.assertEqual(project.titulo, 'Updated')
        self.assertEqual(project.tags, ['API'])
        self.assertEqual(project.usuario, self.worker)

    def test_patch_preserves_tags_and_other_omitted_fields(self):
        project = self.create_project()
        response = self.client.patch(self.detail(project), {'titulo': 'Only title'}, format='json')
        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.tags, ['Django', 'Python'])
        self.assertEqual(project.descricao, 'Descrição profissional')
        self.assertEqual(self.client.get(self.detail(project)).data['tags'], ['Django', 'Python'])

    def test_delete_own_project(self):
        project = self.create_project()
        self.assertEqual(self.client.delete(self.detail(project)).status_code, 204)
        self.assertFalse(Portfolio.objects.filter(pk=project.pk).exists())

    def test_permission_matrix_and_private_reading(self):
        project = self.create_project()
        for actor, read_status, write_status in [
            (self.other, 404, 404),
            (self.company, 404, 403),
            (None, 401, 401),
        ]:
            with self.subTest(actor=actor):
                self.client.force_authenticate(actor)
                self.assertEqual(self.client.get(self.detail(project)).status_code, read_status)
                for method in ['put', 'patch', 'delete']:
                    self.assertEqual(getattr(self.client, method)(self.detail(project)).status_code, write_status)
                if actor != self.other:
                    self.assertEqual(
                        self.client.post(self.url, self.project_data(), format='json').status_code, write_status
                    )
                if actor:
                    self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.worker.groups.clear()
        self.client.force_authenticate(self.worker)
        self.assertEqual(self.client.post(self.url, self.project_data(), format='json').status_code, 403)
        self.assertEqual(self.client.patch(self.detail(project), {}).status_code, 403)

    def test_invalid_fields_and_missing_resource(self):
        for override in [
            {'titulo': ''},
            {'titulo': 'x' * 256},
            {'categoria': 'x' * 101},
            {'descricao': ''},
            {'link': 'javascript:alert(1)'},
            {'link': 'not-a-url'},
        ]:
            with self.subTest(override=override):
                self.assertEqual(
                    self.client.post(self.url, self.project_data(**override), format='json').status_code, 400
                )
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 400)
        self.assertEqual(self.client.get(f'{self.url}999999/').status_code, 404)

    def test_multipart_tags_and_image_persist_as_list(self):
        response = self.client.post(
            self.url,
            self.project_data(
                tags='["Django","Python"," Django "]',
                imagem=image_upload(),
            ),
            format='multipart',
        )
        self.assertEqual(response.status_code, 201, response.data)
        project = Portfolio.objects.get(pk=response.data['id'])
        self.assertEqual(project.tags, ['Django', 'Python'])
        self.assertTrue(Path(self.media.name, project.imagem.name).exists())
        self.assertEqual(response.data['imagem'], f'http://testserver/media/{project.imagem.name}')
        self.assertEqual(self.client.get(self.detail(project)).data['tags'], ['Django', 'Python'])
        self.assertEqual(self.client.get(self.detail(project)).data['imagem'], response.data['imagem'])

    def test_invalid_tags_json_and_multipart(self):
        values = [{}, '[]', [1], [True], [[]], [''], None, ['x'] * 51, ['x' * 101]]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.post(self.url, self.project_data(tags=value), format='json').status_code, 400
                )
        for value in ['[broken', '{}', '[1]', 'null', '"string"']:
            with self.subTest(multipart=value):
                self.assertEqual(
                    self.client.post(self.url, self.project_data(tags=value), format='multipart').status_code, 400
                )

    def test_empty_tags_and_explicit_clearing(self):
        project = self.create_project()
        for encoding, value in [('json', []), ('multipart', '[]')]:
            with self.subTest(encoding=encoding):
                project.tags = ['Original']
                project.save()
                response = self.client.patch(self.detail(project), {'tags': value}, format=encoding)
                self.assertEqual(response.status_code, 200)
                project.refresh_from_db()
                self.assertEqual(project.tags, [])
                self.assertEqual(self.client.get(self.detail(project)).data['tags'], [])
        response = self.client.post(self.url, self.project_data(tags=[]), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['tags'], [])

    def test_portfolio_image_replacement_omission_and_removal(self):
        response = self.client.post(
            self.url,
            self.project_data(
                tags=json.dumps(['Python']),
                imagem=image_upload(),
            ),
            format='multipart',
        )
        project = Portfolio.objects.get(pk=response.data['id'])
        first = project.imagem.name
        self.client.patch(self.detail(project), {'titulo': 'No image change'}, format='json')
        project.refresh_from_db()
        self.assertEqual(project.imagem.name, first)
        response = self.client.patch(self.detail(project), {'imagem': image_upload()}, format='multipart')
        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertNotEqual(project.imagem.name, first)
        self.assertTrue(Path(self.media.name, first).exists())
        last = project.imagem.name
        self.assertEqual(self.client.patch(self.detail(project), {'imagem': ''}, format='multipart').status_code, 200)
        self.assertIsNone(self.client.get(self.detail(project)).data['imagem'])
        self.assertTrue(Path(self.media.name, last).exists())

    def test_portfolio_invalid_image_and_size(self):
        invalid = SimpleUploadedFile('fake.jpg', b'not a jpeg', content_type='image/jpeg')
        self.assertEqual(
            self.client.post(
                self.url,
                self.project_data(
                    tags='[]',
                    imagem=invalid,
                ),
                format='multipart',
            ).status_code,
            400,
        )
        with override_settings(MAX_IMAGE_UPLOAD_BYTES=10):
            self.assertEqual(
                self.client.post(
                    self.url,
                    self.project_data(
                        tags='[]',
                        imagem=image_upload(),
                    ),
                    format='multipart',
                ).status_code,
                400,
            )
        self.assertFalse(Portfolio.objects.exists())

    def test_cloudinary_failure_preserves_existing_project(self):
        project = self.create_project()
        storage = Portfolio._meta.get_field('imagem').storage
        with patch.object(storage, '_save', side_effect=CloudinaryError('private provider details')):
            response = self.client.patch(
                self.detail(project),
                {
                    'titulo': 'Should not persist',
                    'imagem': image_upload(),
                },
                format='multipart',
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private provider', str(response.data))
        project.refresh_from_db()
        self.assertEqual(project.titulo, 'Projeto')
        self.assertFalse(project.imagem)

    def test_remote_portfolio_url_has_no_duplicate_domain(self):
        remote = MediaCloudinaryStorage()
        url = 'https://res.cloudinary.com/test-only/image/upload/portfolios/test-image'
        with (
            patch.object(Portfolio._meta.get_field('imagem'), 'storage', remote),
            patch.object(remote, '_upload', return_value={'public_id': 'portfolios/test-image'}),
            patch.object(remote, 'url', return_value=url),
        ):
            response = self.client.post(
                self.url, self.project_data(tags='[]', imagem=image_upload()), format='multipart'
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['imagem'], url)
