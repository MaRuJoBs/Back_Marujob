# Follow the existing Django integration assertions.
# ruff: noqa: PT009, PT027
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import EmpresaPerfil, User
from core.tests.test_profiles_portfolios import MediaAPITestCase, image_upload
from core.views.empresa_perfil import EmpresaPerfilView


class EmpresaPerfilTests(MediaAPITestCase):
    url = '/api/empresas/me/'
    institutional = {
        'descricao_institucional': 'Soluções digitais para empresas.',
        'area_atuacao': 'Tecnologia',
        'cidade': 'Joinville',
        'uf': 'SC',
        'website': 'https://example.com',
        'contato_comercial': 'comercial@example.com',
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.company.name = 'Empresa antiga'
        cls.company.telefone = 'Contato pessoal privado'
        cls.company.localizacao = 'Endereço privado'
        cls.company.sobre = 'Descrição privada'
        cls.company.profissao = 'Tecnologia'
        cls.company.perfil_configurado = True
        cls.company.latitude = -26
        cls.company.longitude = -48
        cls.company.save()
        cls.other_company = User.objects.create_user('other-company46@example.com', name='Outra empresa')
        cls.other_company.groups.add(Group.objects.get(name='Empresa'))

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.company)

    def test_legacy_company_get_is_private_and_does_not_create_rows(self):
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.company).access_token}')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data,
            {
                'empresa': self.company.pk,
                'name': 'Empresa antiga',
                'profile_image': None,
                **{field: '' for field in self.institutional},
            },
        )
        self.assertEqual(EmpresaPerfil.objects.count(), 0)
        self.assertEqual(set(response.data), {'empresa', 'name', 'profile_image'} | self.institutional.keys())

    def test_patch_creates_persists_and_reuses_name(self):
        response = self.client.patch(self.url, {**self.institutional, 'name': 'MaRuJoB Empresa'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        profile = EmpresaPerfil.objects.get(empresa=self.company)
        for field, value in self.institutional.items():
            self.assertEqual(getattr(profile, field), value)
            self.assertEqual(response.data[field], value)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'MaRuJoB Empresa')
        self.assertEqual(self.company.telefone, 'Contato pessoal privado')
        self.assertEqual(self.company.sobre, 'Descrição privada')
        self.assertEqual(self.client.get(self.url).data, response.data)
        self.assertEqual(self.client.get('/api/usuarios/me/').data['name'], 'MaRuJoB Empresa')

    def test_partial_update_preserves_and_explicit_empty_clears(self):
        self.client.patch(self.url, self.institutional, format='json')
        response = self.client.patch(self.url, {'cidade': 'Curitiba', 'uf': 'PR'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        for field, value in {**self.institutional, 'cidade': 'Curitiba', 'uf': 'PR'}.items():
            self.assertEqual(response.data[field], value)
        cleared = self.client.patch(self.url, {field: '' for field in self.institutional}, format='json')
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(EmpresaPerfil.objects.count(), 1)
        self.assertEqual(cleared.data['name'], 'Empresa antiga')
        for field in self.institutional:
            self.assertEqual(cleared.data[field], '')
        response = self.client.patch(self.url, {'name': ''}, format='json')
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.perfil_configurado)

    def test_role_authentication_and_other_company_isolation(self):
        self.client.patch(self.url, self.institutional, format='json')
        for actor in (None, self.worker, self.other):
            self.client.force_authenticate(actor)
            expected = 401 if actor is None else 403
            self.assertEqual(self.client.get(self.url).status_code, expected)
            self.assertEqual(self.client.patch(self.url, {'name': 'Inválido'}, format='json').status_code, expected)
        self.company.groups.add(Group.objects.get(name='Usuário'))
        self.client.force_authenticate(self.company)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.company.groups.remove(Group.objects.get(name='Usuário'))
        self.client.force_authenticate(self.other_company)
        response = self.client.patch(
            self.url,
            {
                'empresa': self.company.pk,
                'name': 'Nome próprio',
                'contato_comercial': 'Outro contato',
                'email': 'hijack@example.com',
                'is_superuser': True,
                'latitude': 0,
                'perfil_publico': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['empresa'], self.other_company.pk)
        self.company.refresh_from_db()
        self.other_company.refresh_from_db()
        self.assertEqual(self.company.name, 'Empresa antiga')
        self.assertEqual(self.other_company.name, 'Nome próprio')
        self.assertEqual(self.other_company.email, 'other-company46@example.com')
        self.assertFalse(self.other_company.is_superuser)
        self.assertFalse(self.other_company.perfil_publico)
        self.assertEqual(EmpresaPerfil.objects.get(empresa=self.company).contato_comercial, 'comercial@example.com')
        self.assertEqual(self.client.patch(f'/api/empresas/{self.company.pk}/', {}).status_code, 404)
        for method in ('post', 'put', 'delete'):
            self.assertEqual(getattr(self.client, method)(self.url, {}, format='json').status_code, 405)

    def test_validation_rejects_invalid_data_without_partial_writes(self):
        invalid = [
            {'website': 'not-a-url'},
            {'website': 'javascript:alert(1)'},
            {'website': 'ftp://example.com'},
            {'uf': 'XX'},
            {'uf': 'sc'},
            {'uf': ' SC '},
            {'uf': None},
            {'descricao_institucional': 'x' * 2001},
            {'area_atuacao': 'x' * 121},
            {'cidade': 'x' * 101},
            {'contato_comercial': 'x' * 256},
            {'website': 'https://example.com/' + 'x' * 200},
            {'name': 'x' * 256},
            {'cidade': None},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self.client.patch(self.url, {'name': 'Não salvar', **payload}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(next(iter(payload)), response.data)
        self.assertEqual(EmpresaPerfil.objects.count(), 0)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Empresa antiga')
        for website in ('http://example.com', 'https://example.com'):
            self.assertEqual(self.client.patch(self.url, {'website': website}, format='json').status_code, 200)

    def test_logo_upload_validation_removal_and_storage_failure(self):
        response = self.client.patch(
            self.url,
            {
                'profile_image': image_upload(),
                'area_atuacao': 'Tecnologia',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['profile_image'].startswith('http://testserver/'))
        self.company.refresh_from_db()
        self.assertTrue(self.company.profile_image)
        old_name = self.company.profile_image.name
        bad = SimpleUploadedFile('fake.png', b'not-an-image', content_type='image/png')
        self.assertEqual(self.client.patch(self.url, {'profile_image': bad}, format='multipart').status_code, 400)
        with patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('private storage detail')):
            failed = self.client.patch(
                self.url,
                {
                    'profile_image': image_upload('new.png'),
                    'name': 'Não salvar',
                    'area_atuacao': 'Não salvar',
                },
                format='multipart',
            )
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn('private storage detail', str(failed.data))
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Empresa antiga')
        self.assertEqual(self.company.profile_image.name, old_name)
        self.assertEqual(EmpresaPerfil.objects.get(empresa=self.company).area_atuacao, 'Tecnologia')
        cleared = self.client.patch(self.url, {'profile_image': None}, format='json')
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.data['profile_image'])

    def test_openapi_exposes_only_the_private_profile_contract(self):
        schema = SchemaGenerator(patterns=[path('api/empresas/me/', EmpresaPerfilView.as_view())]).get_schema(
            public=True
        )
        self.assertEqual(set(schema['paths']['/api/empresas/me/']), {'get', 'patch'})
        fields = schema['components']['schemas']['EmpresaPerfil']['properties']
        self.assertEqual(set(fields), {'empresa', 'name', 'profile_image'} | self.institutional.keys())
        self.assertTrue(fields['empresa']['readOnly'])
        self.assertEqual(fields['website']['format'], 'uri')


class EmpresaPerfilMigrationTests(TransactionTestCase):
    def test_new_table_preserves_existing_users_and_b45_publication(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('core', '0021_publicacao_perfil_portfolio'), ('core', '0021_freelance_contrato_b47')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            old_users = apps.get_model('core', 'User')
            company = old_users.objects.create(email='migration46-company@example.com', name='Empresa antiga')
            worker = old_users.objects.create(
                email='migration46-worker@example.com',
                perfil_publico=True,
                cidade_publica='Joinville',
            )
            project = apps.get_model('core', 'Portfolio').objects.create(usuario=worker, publico=True, titulo='Projeto')
            snapshot = list(old_users.objects.order_by('id').values())
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(list(User.objects.order_by('id').values()), snapshot)
            self.assertEqual(EmpresaPerfil.objects.count(), 0)
            profile = EmpresaPerfil.objects.create(empresa_id=company.pk)
            self.assertEqual(profile.contato_comercial, '')
            self.assertEqual(profile.cidade, '')
            updated_apps = MigrationExecutor(connection).loader.project_state(latest).apps
            self.assertTrue(updated_apps.get_model('core', 'Portfolio').objects.get(pk=project.pk).publico)
            self.assertTrue(User.objects.get(pk=worker.pk).perfil_publico)
        finally:
            MigrationExecutor(connection).migrate(latest)
