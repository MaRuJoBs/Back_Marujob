"""Company location contract, permissions, privacy and migration preservation."""

# ruff: noqa: PT009, PT027
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase

from core.models import EmpresaPerfil, User
from core.serializers.empresa_perfil import EmpresaPerfilSerializer
from core.views.empresa_perfil import EmpresaLocalizacaoPublicaView

PRIVATE_URL = '/api/empresas/me/'
PASSWORD = 'Synthetic-B59-829173!'


def public_url(company):
    return f'/api/empresas/{company.pk}/localizacao/'


class EmpresaLocalizacaoFixtures(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company_a = User.objects.create_user('company-a@b59.example.invalid', PASSWORD, name='Company A')
        cls.company_b = User.objects.create_user('company-b@b59.example.invalid', PASSWORD, name='Company B')
        cls.worker = User.objects.create_user('worker@b59.example.invalid', PASSWORD)
        company_group = Group.objects.get(name='Empresa')
        cls.company_a.groups.add(company_group)
        cls.company_b.groups.add(company_group)
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.company_a.localizacao = 'Synthetic private full address'
        cls.company_a.latitude = -26.31
        cls.company_a.longitude = -48.84
        cls.company_a.telefone = 'Synthetic private phone'
        cls.company_a.save()

    def setUp(self):
        self.client.force_authenticate(self.company_a)

    def patch_location(self, **payload):
        return self.client.patch(PRIVATE_URL, payload, format='json')

    def save_location(self, **extras):
        response = self.patch_location(cidade='Joinville', uf='SC', **extras)
        self.assertEqual(response.status_code, 200, response.data)
        return response


class EmpresaLocalizacaoTests(EmpresaLocalizacaoFixtures):
    def test_f58_payload_without_optional_fields_is_persisted(self):
        response = self.save_location()
        profile = EmpresaPerfil.objects.get(empresa=self.company_a)
        self.assertEqual((profile.cidade, profile.uf, profile.pais, profile.bairro), ('Joinville', 'SC', 'BR', ''))
        self.assertEqual(response.data['pais'], 'BR')
        self.assertEqual(self.client.get(PRIVATE_URL).data, response.data)
        self.company_a.refresh_from_db()
        self.assertEqual(self.company_a.localizacao, 'Synthetic private full address')
        self.assertEqual((self.company_a.latitude, self.company_a.longitude), (-26.31, -48.84))

    def test_optional_country_and_neighborhood(self):
        response = self.save_location(pais='BR', bairro='Centro')
        self.assertEqual(response.data['bairro'], 'Centro')
        profile = EmpresaPerfil.objects.get(empresa=self.company_a)
        profile.refresh_from_db()
        self.assertEqual(profile.bairro, 'Centro')
        self.assertEqual(profile.pais, 'BR')
        self.assertNotIn('pais', {field.name for field in EmpresaPerfil._meta.fields})

    def test_fresh_login_after_logout_reads_the_persisted_location(self):
        client = APIClient()
        token = client.post('/api/token/', {'email': self.company_a.email, 'password': PASSWORD}).data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(client.patch(PRIVATE_URL, {'cidade': 'Joinville', 'uf': 'SC'}, format='json').status_code, 200)
        client.credentials()
        self.assertEqual(client.get(PRIVATE_URL).status_code, 401)
        new_client = APIClient()
        login = new_client.post('/api/token/', {'email': self.company_a.email, 'password': PASSWORD})
        self.assertEqual(login.status_code, 200)
        new_client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
        response = new_client.get(PRIVATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['cidade'], response.data['uf']), ('Joinville', 'SC'))
        self.assertEqual(response.data['pais'], 'BR')

    def test_updates_and_partial_patch_preserve_unrelated_fields(self):
        self.save_location(bairro='Centro', descricao_institucional='Synthetic institution')
        response = self.patch_location(bairro='Bucarein')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['cidade'], response.data['uf']), ('Joinville', 'SC'))
        response = self.patch_location(cidade='Curitiba', uf='PR', bairro='Batel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['bairro'], 'Batel')
        self.assertEqual(response.data['descricao_institucional'], 'Synthetic institution')
        response = self.patch_location(name='Updated company')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (response.data['cidade'], response.data['uf'], response.data['bairro']), ('Curitiba', 'PR', 'Batel')
        )

    def test_changing_city_or_state_discards_omitted_obsolete_neighborhood(self):
        self.save_location(bairro='Centro')
        response = self.patch_location(cidade='Blumenau')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (response.data['cidade'], response.data['uf'], response.data['bairro']), ('Blumenau', 'SC', '')
        )

    def test_explicit_removal_clears_the_complete_location(self):
        self.save_location(bairro='Centro')
        response = self.patch_location(cidade='', uf='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {key: response.data[key] for key in ('cidade', 'uf', 'pais', 'bairro')},
            {'cidade': '', 'uf': '', 'pais': '', 'bairro': ''},
        )
        self.assertEqual(self.client.get(public_url(self.company_a)).data, {'cidade': '', 'uf': ''})

    def test_malformed_values_are_rejected_without_partial_writes(self):
        invalid = [
            {'cidade': 123, 'uf': 'SC'},
            {'cidade': True, 'uf': 'SC'},
            {'cidade': [], 'uf': 'SC'},
            {'cidade': {}, 'uf': 'SC'},
            {'cidade': None, 'uf': 'SC'},
            {'cidade': '123', 'uf': 'SC'},
            {'cidade': '<script>synthetic</script>', 'uf': 'SC'},
            {'cidade': 'Join\nville', 'uf': 'SC'},
            {'cidade': 'Join\tville', 'uf': 'SC'},
            {'cidade': 'x' * 101, 'uf': 'SC'},
            {'cidade': 'Joinville', 'uf': 'XX'},
            {'cidade': 'Joinville', 'uf': 'sc'},
            {'cidade': 'Joinville', 'uf': ' SC '},
            {'cidade': 'Joinville', 'uf': None},
            {'cidade': 'Joinville', 'uf': 'SC', 'pais': 'US'},
            {'cidade': 'Joinville', 'uf': 'SC', 'pais': 'Brasil'},
            {'cidade': 'Joinville', 'uf': 'SC', 'pais': ''},
            {'cidade': 'Joinville', 'uf': 'SC', 'pais': None},
            {'cidade': 'Joinville', 'uf': 'SC', 'bairro': []},
            {'cidade': 'Joinville', 'uf': 'SC', 'bairro': 123},
            {'cidade': 'Joinville', 'uf': 'SC', 'bairro': None},
            {'cidade': 'Joinville', 'uf': 'SC', 'bairro': 'x' * 101},
        ]
        for payload in invalid:
            with self.subTest(fields=list(payload)):
                response = self.patch_location(name='Must not save', **payload)
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(EmpresaPerfil.objects.exists())
        self.company_a.refresh_from_db()
        self.assertEqual(self.company_a.name, 'Company A')

    def test_city_and_state_are_required_together_but_full_removal_is_supported(self):
        for payload in [
            {'cidade': 'Joinville'},
            {'uf': 'SC'},
            {'cidade': '', 'uf': 'SC'},
            {'cidade': 'Joinville', 'uf': ''},
            {'bairro': 'Centro'},
            {'pais': 'BR'},
            {'cidade': '   ', 'uf': 'SC'},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.patch_location(**payload).status_code, 400)
        self.save_location()
        for payload in [{'cidade': ''}, {'uf': ''}]:
            self.assertEqual(self.patch_location(**payload).status_code, 400)
        self.assertEqual(self.patch_location(cidade='', uf='', pais='', bairro='').status_code, 200)

    def test_partial_update_rechecks_current_profile_under_the_parent_lock(self):
        self.save_location()
        stale = EmpresaPerfil.objects.get(empresa=self.company_a)
        serializer = EmpresaPerfilSerializer(stale, data={'bairro': 'Centro'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        EmpresaPerfil.objects.filter(empresa=self.company_a).update(cidade='', uf='')
        with self.assertRaises(ValidationError):
            serializer.save()
        self.assertEqual(EmpresaPerfil.objects.get(empresa=self.company_a).bairro, '')

    def test_unrelated_patch_keeps_a_legacy_incomplete_location_unchanged(self):
        EmpresaPerfil.objects.create(empresa=self.company_a, cidade='Joinville')
        response = self.patch_location(name='Updated company')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['cidade'], response.data['uf']), ('Joinville', ''))
        self.assertEqual(self.patch_location(bairro='Centro').status_code, 400)

    def test_legacy_company_get_does_not_create_or_copy_precise_location(self):
        response = self.client.get(PRIVATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {key: response.data[key] for key in ('cidade', 'uf', 'pais', 'bairro')},
            {'cidade': '', 'uf': '', 'pais': '', 'bairro': ''},
        )
        self.assertFalse(EmpresaPerfil.objects.exists())

    def test_company_cannot_target_another_company_or_change_protected_fields(self):
        self.save_location(bairro='Centro')
        original = EmpresaPerfil.objects.get(empresa=self.company_a)
        self.client.force_authenticate(self.company_b)
        response = self.patch_location(
            empresa=self.company_a.pk,
            user_id=self.company_a.pk,
            cidade='Curitiba',
            uf='PR',
            email='must-not-save@b59.example.invalid',
            groups=[],
            is_superuser=True,
            latitude=91,
            longitude=181,
            localizacao='Must not save',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['empresa'], self.company_b.pk)
        original.refresh_from_db()
        self.assertEqual((original.cidade, original.uf, original.bairro), ('Joinville', 'SC', 'Centro'))
        self.company_b.refresh_from_db()
        self.assertEqual(self.company_b.email, 'company-b@b59.example.invalid')
        self.assertFalse(self.company_b.is_superuser)
        self.assertIsNone(self.company_b.latitude)
        self.assertIsNone(self.company_b.longitude)
        self.assertEqual(self.company_b.localizacao, '')
        self.assertEqual(self.client.patch(public_url(self.company_a), {'cidade': 'Other'}).status_code, 405)
        self.assertEqual(self.client.patch(f'/api/empresas/{self.company_a.pk}/', {}).status_code, 404)

    def test_freelancer_and_anonymous_requests_cannot_modify_company_location(self):
        self.save_location(bairro='Centro')
        for actor, expected in [(self.worker, 403), (None, 401)]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.patch_location(cidade='Curitiba', uf='PR').status_code, expected)
            self.assertEqual(self.client.get(PRIVATE_URL).status_code, expected)
        profile = EmpresaPerfil.objects.get(empresa=self.company_a)
        self.assertEqual((profile.cidade, profile.uf, profile.bairro), ('Joinville', 'SC', 'Centro'))

    def test_inactive_or_ambiguous_company_cannot_edit(self):
        self.company_a.groups.add(Group.objects.get(name='Usuário'))
        self.assertEqual(self.patch_location(cidade='Joinville', uf='SC').status_code, 403)
        self.company_a.groups.remove(Group.objects.get(name='Usuário'))
        self.company_a.is_active = False
        self.company_a.save(update_fields=['is_active'])
        self.assertEqual(self.patch_location(cidade='Joinville', uf='SC').status_code, 403)
        self.assertFalse(EmpresaPerfil.objects.exists())

    def test_public_location_uses_only_an_explicit_city_state_projection(self):
        self.save_location(bairro='Synthetic private neighborhood', contato_comercial='Synthetic private contact')
        for actor in [None, self.worker, self.company_b]:
            self.client.force_authenticate(actor)
            response = self.client.get(public_url(self.company_a))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {'cidade': 'Joinville', 'uf': 'SC'})
            for marker in ['Synthetic private', self.company_a.email, 'latitude', 'longitude', 'bairro', 'telefone']:
                self.assertNotIn(marker, response.content.decode())

    def test_public_location_does_not_fetch_private_columns_or_write_legacy_rows(self):
        self.client.force_authenticate(None)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(public_url(self.company_a))
        self.assertEqual(response.data, {'cidade': '', 'uf': ''})
        self.assertFalse(EmpresaPerfil.objects.exists())
        sql = ' '.join(query['sql'] for query in queries.captured_queries).lower()
        for private_column in ['latitude', 'longitude', 'bairro', 'email', 'telefone', 'password', 'contato_comercial']:
            self.assertNotIn(private_column, sql)

    def test_public_route_hides_ineligible_companies_and_rejects_writes(self):
        self.client.force_authenticate(None)
        for user in [self.worker, self.company_b]:
            if user == self.company_b:
                user.is_active = False
                user.save(update_fields=['is_active'])
            self.assertEqual(self.client.get(public_url(user)).status_code, 404)
        for value in [0, 2**63, 2**200]:
            self.assertEqual(self.client.get(f'/api/empresas/{value}/localizacao/').status_code, 404)
        for method in ['post', 'put', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)(public_url(self.company_a), {}).status_code, 405)

    def test_public_location_hides_ambiguous_and_administrative_accounts(self):
        self.client.force_authenticate(None)
        self.company_a.groups.add(Group.objects.get(name='Usuário'))
        self.assertEqual(self.client.get(public_url(self.company_a)).status_code, 404)
        self.company_a.groups.remove(Group.objects.get(name='Usuário'))
        self.company_a.is_staff = True
        self.company_a.save(update_fields=['is_staff'])
        self.assertEqual(self.client.get(public_url(self.company_a)).status_code, 404)

    def test_format_validation_does_not_claim_geographic_verification(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No geocoding in B59')):
            response = self.patch_location(cidade='Cidade Sintética', uf='SC', pais='BR')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('verificada', response.data)

    def test_multipart_location_remains_compatible_with_profile_updates(self):
        response = self.client.patch(
            PRIVATE_URL, {'cidade': 'Joinville', 'uf': 'SC', 'name': 'Multipart company'}, format='multipart'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['cidade'], response.data['uf']), ('Joinville', 'SC'))


class EmpresaLocalizacaoSchemaTests(SimpleTestCase):
    def test_public_schema_contains_only_city_state_and_read_operations(self):
        schema = SchemaGenerator(
            patterns=[
                path('api/empresas/<int:empresa_id>/localizacao/', EmpresaLocalizacaoPublicaView.as_view()),
            ]
        ).get_schema(public=True)
        operations = schema['paths']['/api/empresas/{empresa_id}/localizacao/']
        self.assertEqual(set(operations), {'get'})
        fields = schema['components']['schemas']['EmpresaLocalizacaoPublica']['properties']
        self.assertEqual(set(fields), {'cidade', 'uf'})


class EmpresaLocalizacaoMigrationTests(TransactionTestCase):
    def test_optional_neighborhood_migration_preserves_existing_records(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('core', '0023_avaliacoes_reputacao'), ('chat', '0001_initial')]
        try:
            executor.migrate(previous)
            old_apps = executor.loader.project_state(previous).apps
            user = old_apps.get_model('core', 'User').objects.create(
                email='migration@b59.example.invalid', name='Legacy company'
            )
            profile_model = old_apps.get_model('core', 'EmpresaPerfil')
            profile = profile_model.objects.create(
                empresa_id=user.pk, cidade='Joinville', uf='SC', contato_comercial='Synthetic commercial contact'
            )
            before = profile_model.objects.values().get(pk=profile.pk)
            MigrationExecutor(connection).migrate(latest)
            after = EmpresaPerfil.objects.values().get(pk=profile.pk)
            self.assertEqual(after.pop('bairro'), '')
            self.assertEqual(after, before)
            self.assertEqual(EmpresaPerfil.objects.count(), 1)
            self.assertEqual(User.objects.get(pk=user.pk).name, 'Legacy company')
        finally:
            MigrationExecutor(connection).migrate(latest)
