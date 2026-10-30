# Follow the project's Django integration assertions.
# ruff: noqa: PT009, PT027
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from core.models import Candidatura, Favorito, Freelance, Notificacao, User


class FreelanceComplementTests(APITestCase):  # noqa: PLR0904 -- opportunity integration scenarios
    url = '/api/freelances/'
    old_fields = {'id', 'empresa', 'titulo', 'descricao', 'tag', 'preco', 'tempo'}
    text_fields = {'requisitos', 'beneficios', 'tipo_contratacao', 'nivel_experiencia', 'jornada_trabalho'}
    nullable_fields = {'data_publicacao', 'salario_minimo', 'salario_maximo'}
    complete_data = {
        'titulo': 'Desenvolver uma página',
        'descricao': 'Modalidade: Remoto\n\nDesenvolvimento de uma página responsiva.',
        'tag': 'Desenvolvimento Web',
        'preco': '1500.00',
        'tempo': '40',
        'requisitos': 'Conhecimento em Vue e acessibilidade.',
        'beneficios': 'Horário flexível.',
        'tipo_contratacao': 'PJ',
        'nivel_experiencia': 'Pleno',
        'jornada_trabalho': 'Segunda a sexta, das 9h às 18h',
        'data_publicacao': '2026-10-30',
        'salario_minimo': '2000.50',
        'salario_maximo': '3500.00',
    }

    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('complement-company@example.com', 'Secure-Complement-392!')
        cls.other = User.objects.create_user('complement-other@example.com')
        cls.worker = User.objects.create_user('complement-worker@example.com')
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.other.groups.add(Group.objects.get(name='Empresa'))
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.job = Freelance.objects.create(empresa=cls.company, **cls.complete_data)

    def setUp(self):
        self.client.force_authenticate(self.company)
        self.job.refresh_from_db()
        self.detail_url = f'{self.url}{self.job.pk}/'

    def minimal_data(self, **extra):
        return {'titulo': 'Vaga compatível', 'descricao': '', 'tag': '', 'preco': '0.00', 'tempo': '1 dia', **extra}

    def assert_complete(self, data):
        self.assertEqual(set(data), self.old_fields | self.text_fields | self.nullable_fields)

    def test_create_without_complements_preserves_previous_contract(self):
        response = self.client.post(self.url, self.minimal_data(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assert_complete(response.data)
        job = Freelance.objects.get(pk=response.data['id'])
        for field in self.text_fields:
            self.assertEqual(response.data[field], '')
            self.assertEqual(getattr(job, field), '')
        for field in self.nullable_fields:
            self.assertIsNone(response.data[field])
            self.assertIsNone(getattr(job, field))
        self.assertEqual(response.data['preco'], '0.00')

    def test_create_all_fields_persists_and_returns_complete_values(self):
        response = self.client.post(self.url, self.complete_data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assert_complete(response.data)
        for field, value in self.complete_data.items():
            self.assertEqual(response.data[field], value)
        job = Freelance.objects.get(pk=response.data['id'])
        self.assertEqual(job.empresa, self.company)
        self.assertEqual(job.data_publicacao, date(2026, 10, 30))
        self.assertEqual(job.salario_minimo, Decimal('2000.50'))
        self.assertEqual(job.salario_maximo, Decimal('3500.00'))
        for field in self.text_fields:
            self.assertEqual(getattr(job, field), self.complete_data[field])
        self.assertEqual(job.preco, Decimal('1500.00'))
        self.assertEqual(job.tempo, '40')
        self.assertEqual(job.descricao, self.complete_data['descricao'])
        self.assertEqual(self.client.get(f'{self.url}{job.pk}/').data, response.data)

    def test_detail_and_paginated_list_include_every_complement(self):
        self.client.force_authenticate(self.worker)
        detail = self.client.get(self.detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assert_complete(detail.data)
        for field, value in self.complete_data.items():
            self.assertEqual(detail.data[field], value)
        for index in range(11):
            Freelance.objects.create(empresa=self.other, **self.minimal_data(titulo=f'Vaga {index}'))
        response = self.client.get(self.url)
        self.assertEqual(set(response.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['count'], 12)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['results'][0], detail.data)
        self.assertIsNotNone(response.data['next'])
        second = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(second.data['results']), 2)
        for item in response.data['results'] + second.data['results']:
            self.assert_complete(item)

    def test_patch_changes_sent_field_and_preserves_omitted_fields(self):
        response = self.client.patch(self.detail_url, {'beneficios': 'Benefício revisado'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assert_complete(response.data)
        self.job.refresh_from_db()
        for field, value in self.complete_data.items():
            if field != 'beneficios':
                self.assertEqual(response.data[field], value)
        self.assertEqual(self.job.beneficios, 'Benefício revisado')
        self.assertEqual(self.client.get(self.detail_url).data, response.data)

    def test_patch_updates_all_complements(self):
        data = {
            'requisitos': 'Revisados',
            'beneficios': 'Revisados',
            'tipo_contratacao': 'CLT',
            'nivel_experiencia': 'Sênior',
            'jornada_trabalho': '30 horas semanais',
            'data_publicacao': '2030-12-25',
            'salario_minimo': '4000.05',
            'salario_maximo': '5000.50',
        }
        response = self.client.patch(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assert_complete(response.data)
        self.job.refresh_from_db()
        for field, value in data.items():
            self.assertEqual(response.data[field], value)
        self.assertEqual(self.job.data_publicacao, date(2030, 12, 25))
        self.assertEqual(self.job.salario_minimo, Decimal('4000.05'))
        self.assertEqual(self.job.salario_maximo, Decimal('5000.50'))
        self.assertEqual(self.job.preco, Decimal('1500.00'))
        self.assertEqual(self.job.tempo, '40')

    def test_patch_clears_text_date_and_range_explicitly(self):
        data = {field: '' for field in self.text_fields}
        data.update({field: None for field in self.nullable_fields})
        response = self.client.patch(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.job.refresh_from_db()
        for field, value in data.items():
            self.assertEqual(response.data[field], value)
            self.assertEqual(getattr(self.job, field), value)

    def test_incomplete_negative_inverted_or_imprecise_range_is_rejected(self):
        for data, field in [
            ({'salario_minimo': '10'}, 'salario_maximo'),
            ({'salario_maximo': '10'}, 'salario_minimo'),
            ({'salario_minimo': '10', 'salario_maximo': None}, 'salario_maximo'),
            ({'salario_minimo': '-0.01', 'salario_maximo': '10'}, 'salario_minimo'),
            ({'salario_minimo': '0', 'salario_maximo': '-1'}, 'salario_maximo'),
            ({'salario_minimo': '10', 'salario_maximo': '9'}, 'salario_maximo'),
            ({'salario_minimo': '0.001', 'salario_maximo': '10'}, 'salario_minimo'),
            ({'salario_minimo': '0', 'salario_maximo': '1.001'}, 'salario_maximo'),
            ({'salario_minimo': '0', 'salario_maximo': '100000000.00'}, 'salario_maximo'),
            ({'salario_minimo': 'NaN', 'salario_maximo': '10'}, 'salario_minimo'),
            ({'salario_minimo': '0', 'salario_maximo': 'Infinity'}, 'salario_maximo'),
        ]:
            with self.subTest(data=data):
                response = self.client.post(self.url, self.minimal_data(**data), format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertEqual(Freelance.objects.count(), 1)

    def test_valid_range_boundaries_and_two_decimal_output(self):
        for minimum, maximum, expected_minimum, expected_maximum in [
            ('0', '99999999.99', '0.00', '99999999.99'),
            ('0', '0', '0.00', '0.00'),
            ('10.5', '10.5', '10.50', '10.50'),
        ]:
            with self.subTest(minimum=minimum, maximum=maximum):
                response = self.client.post(
                    self.url,
                    self.minimal_data(
                        salario_minimo=minimum,
                        salario_maximo=maximum,
                    ),
                    format='json',
                )
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data['salario_minimo'], expected_minimum)
                self.assertEqual(response.data['salario_maximo'], expected_maximum)

    def test_partial_range_patch_validates_final_stored_state(self):
        response = self.client.patch(self.detail_url, {'salario_minimo': '3000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['salario_maximo'], '3500.00')
        for data, field in [
            ({'salario_maximo': '2500'}, 'salario_maximo'),
            ({'salario_minimo': '3600'}, 'salario_maximo'),
            ({'salario_minimo': None}, 'salario_minimo'),
            ({'salario_maximo': None}, 'salario_maximo'),
        ]:
            with self.subTest(data=data):
                response = self.client.patch(self.detail_url, data, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.salario_minimo, Decimal('3000'))
        self.assertEqual(self.job.salario_maximo, Decimal('3500'))
        response = self.client.patch(
            self.detail_url,
            {
                'salario_minimo': None,
                'salario_maximo': None,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(self.detail_url, {'salario_maximo': '100'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('salario_minimo', response.data)

    def test_inverted_range_error_matches_frontend_field(self):
        response = self.client.patch(self.detail_url, {'salario_maximo': '1000'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'salario_maximo': ['O valor máximo deve ser maior ou igual ao mínimo.']})

    def test_text_limits_and_invalid_options_and_dates(self):
        for field, limit in [('requisitos', 1000), ('beneficios', 1000), ('jornada_trabalho', 100)]:
            response = self.client.patch(self.detail_url, {field: 'x' * limit}, format='json')
            self.assertEqual(response.status_code, 200)
            response = self.client.patch(self.detail_url, {field: 'x' * (limit + 1)}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data)
        for data in [
            {'tipo_contratacao': 'pj'},
            {'tipo_contratacao': 'Autonomo'},
            {'nivel_experiencia': 'Junior'},
            {'nivel_experiencia': 'Diretor'},
            {'data_publicacao': '30/10/2026'},
            {'data_publicacao': '2026-02-30'},
            {'data_publicacao': '2026-13-01'},
            {'data_publicacao': ''},
            {'data_publicacao': '2026-10-30T12:00:00Z'},
            {'data_publicacao': '2026-1-01'},
            {'data_publicacao': '20261030'},
        ]:
            with self.subTest(data=data):
                response = self.client.patch(self.detail_url, data, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(next(iter(data)), response.data)

    def test_all_documented_options_are_accepted(self):
        for field, values in [
            ('tipo_contratacao', ['CLT', 'PJ', 'Autônomo', 'Temporário', 'Estágio', 'Outros']),
            ('nivel_experiencia', ['Iniciante', 'Júnior', 'Pleno', 'Sênior', 'Especialista']),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.client.patch(self.detail_url, {field: value}, format='json')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data[field], value)

    def test_free_text_whitespace_is_preserved_for_frontend_confirmation(self):
        data = {
            'requisitos': '  Requisitos\nDetalhes.  ',
            'beneficios': '\nFlexível\n',
            'jornada_trabalho': '  30 horas  ',
        }
        response = self.client.patch(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        for field, value in data.items():
            self.assertEqual(response.data[field], value)
            self.assertEqual(getattr(self.job, field), value)

    def test_old_price_is_still_required_and_validated(self):
        data = self.minimal_data(salario_minimo='100', salario_maximo='200')
        del data['preco']
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('preco', response.data)
        response = self.client.patch(self.detail_url, {'preco': '-1'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('preco', response.data)

    def test_owner_cannot_be_transferred_by_post_patch_or_put(self):
        response = self.client.post(self.url, self.minimal_data(empresa=self.other.pk), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['empresa'], self.company.pk)
        response = self.client.patch(
            self.detail_url, {'empresa': self.other.pk, 'beneficios': 'Revisado'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['empresa'], self.company.pk)
        response = self.client.put(self.detail_url, self.minimal_data(empresa=self.other.pk), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['empresa'], self.company.pk)
        self.assertEqual(response.data['salario_minimo'], '2000.50')

    def test_other_company_and_freelancer_cannot_write(self):
        for actor in [self.other, self.worker]:
            self.client.force_authenticate(actor)
            self.assertEqual(
                self.client.patch(self.detail_url, {'beneficios': 'Hacked'}, format='json').status_code, 403
            )
            self.assertEqual(self.client.put(self.detail_url, self.minimal_data(), format='json').status_code, 403)
            self.assertEqual(self.client.delete(self.detail_url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.minimal_data(), format='json').status_code, 403)
        self.job.refresh_from_db()
        self.assertEqual(self.job.beneficios, self.complete_data['beneficios'])

    def test_jwt_login_and_unauthenticated_access(self):
        client = APIClient()
        token = client.post(
            '/api/token/',
            {
                'email': self.company.email,
                'password': 'Secure-Complement-392!',
            },
            format='json',
        )
        self.assertEqual(token.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.data["access"]}')
        self.assertEqual(client.post(self.url, self.minimal_data(), format='json').status_code, 201)
        client.credentials()
        self.assertEqual(client.get(self.url).status_code, 401)
        self.assertEqual(client.patch(self.detail_url, {}, format='json').status_code, 401)

    def test_applications_favorites_and_notifications_survive_edit(self):
        self.client.force_authenticate(self.worker)
        response = self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        application = Candidatura.objects.get(pk=response.data['id'])
        notification = Notificacao.objects.get(candidatura=application)
        favorite = Favorito.objects.create(usuario=self.worker, oportunidade=self.job)
        self.client.force_authenticate(self.company)
        self.assertEqual(self.client.patch(self.detail_url, {'beneficios': 'Novo'}, format='json').status_code, 200)
        self.assertTrue(Candidatura.objects.filter(pk=application.pk, status='pendente').exists())
        self.assertTrue(Notificacao.objects.filter(pk=notification.pk, lida=False).exists())
        self.assertTrue(Favorito.objects.filter(pk=favorite.pk).exists())
        self.client.force_authenticate(self.worker)
        self.assertEqual(
            self.client.get(f'/api/candidaturas/{application.pk}/').data['oportunidade_detalhes']['beneficios'], 'Novo'
        )
        self.assertEqual(
            self.client.get('/api/favoritos/').data['results'][0]['oportunidade_detalhes']['salario_minimo'], '2000.50'
        )
        self.client.force_authenticate(self.company)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 204)
        self.assertFalse(Candidatura.objects.filter(pk=application.pk).exists())
        self.assertFalse(Notificacao.objects.filter(pk=notification.pk).exists())
        self.assertFalse(Favorito.objects.filter(pk=favorite.pk).exists())


class FreelanceComplementMigrationTests(TransactionTestCase):
    def test_existing_opportunity_and_relationships_survive_migration(self):
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        previous = [('core', '0019_notificacoes_retroativas')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            old_users = apps.get_model('core', 'User')
            company = old_users.objects.create(email='migration-complement-company@example.com', password='!')
            worker = old_users.objects.create(email='migration-complement-worker@example.com', password='!')
            job = apps.get_model('core', 'Freelance').objects.create(
                empresa=company,
                titulo='Legada',
                descricao='Modalidade: Remoto\n\nDescrição',
                tag='Web',
                preco='1500.00',
                tempo='40',
            )
            application = apps.get_model('core', 'Candidatura').objects.create(
                freelancer=worker,
                oportunidade=job,
                status='aprovada',
            )
            notification = apps.get_model('core', 'Notificacao').objects.create(
                empresa=company,
                candidatura=application,
                lida=True,
            )
            favorite = apps.get_model('core', 'Favorito').objects.create(usuario=worker, oportunidade=job)
            MigrationExecutor(connection).migrate(latest_targets)
            updated = Freelance.objects.get(pk=job.pk)
            self.assertEqual(updated.empresa_id, company.pk)
            self.assertEqual(updated.titulo, 'Legada')
            self.assertEqual(updated.preco, Decimal('1500.00'))
            self.assertEqual(updated.tempo, '40')
            self.assertEqual(updated.descricao, 'Modalidade: Remoto\n\nDescrição')
            for field in FreelanceComplementTests.text_fields:
                self.assertEqual(getattr(updated, field), '')
            for field in FreelanceComplementTests.nullable_fields:
                self.assertIsNone(getattr(updated, field))
            self.assertEqual(Candidatura.objects.get(pk=application.pk).status, 'aprovada')
            self.assertTrue(Notificacao.objects.get(pk=notification.pk).lida)
            self.assertEqual(Favorito.objects.get(pk=favorite.pk).oportunidade_id, job.pk)
        finally:
            MigrationExecutor(connection).migrate(latest_targets)
