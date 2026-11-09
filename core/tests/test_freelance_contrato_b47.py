# Django integration assertions follow the existing suite.
# ruff: noqa: PT009, PT027
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase

from core.models import Candidatura, Favorito, Freelance, Notificacao, User
from core.views.freelance import FreelanceViewSet


class OpportunityContractTests(APITestCase):
    url = '/api/freelances/'
    base = {'titulo': 'Projeto B47', 'preco': '1500.00', 'tempo': '40'}
    structured = {'modalidade': 'Híbrido', 'cidade': 'São Paulo', 'uf': 'SP', 'status': 'publicada'}

    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('b47-company@example.com', 'test-b47-password')
        cls.other = User.objects.create_user('b47-other@example.com')
        cls.worker = User.objects.create_user('b47-worker@example.com')
        for company in (cls.company, cls.other):
            company.groups.add(Group.objects.get(name='Empresa'))
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.job = Freelance.objects.create(
            empresa=cls.company,
            descricao='Modalidade: Remoto\n\nTexto original.',
            tag='Web',
            requisitos='Vue',
            salario_minimo='2000.50',
            salario_maximo='3500.00',
            **cls.base,
            **cls.structured,
        )

    def setUp(self):
        self.client.force_authenticate(self.company)
        self.detail = f'{self.url}{self.job.pk}/'

    def test_post_persistence_detail_and_list(self):
        response = self.client.post(self.url, {**self.base, **self.structured}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        job = Freelance.objects.get(pk=response.data['id'])
        for field, value in self.structured.items():
            self.assertEqual(getattr(job, field), value)
            self.assertEqual(response.data[field], value)
        self.assertEqual(job.empresa, self.company)
        self.assertEqual(self.client.get(f'{self.url}{job.pk}/').data, response.data)
        self.assertIn(response.data, self.client.get(self.url).data['results'])

    def test_old_post_defaults_without_description_inference(self):
        data = {**self.base, 'descricao': 'Modalidade: Presencial\n\nTexto legado.'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'publicada')
        for field in ('modalidade', 'cidade', 'uf'):
            self.assertEqual(response.data[field], '')
        self.assertEqual(response.data['descricao'], data['descricao'])

    def test_put_and_patch_preserve_omitted_values(self):
        self.client.patch(self.detail, {'status': 'encerrada'}, format='json')
        for method in ('put', 'patch'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.detail, self.base, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                for field, value in {**self.structured, 'status': 'encerrada'}.items():
                    self.assertEqual(response.data[field], value)
                self.assertEqual(response.data['descricao'], 'Modalidade: Remoto\n\nTexto original.')
                self.assertEqual(response.data['requisitos'], 'Vue')
                self.assertEqual(response.data['salario_minimo'], '2000.50')
                self.assertEqual(response.data['empresa'], self.company.pk)

    def test_put_and_patch_update_structured_fields(self):
        for method, status in [('put', 'cancelada'), ('patch', 'encerrada')]:
            payload = {**self.base, 'modalidade': 'Presencial', 'cidade': 'Curitiba', 'uf': 'PR', 'status': status}
            response = getattr(self.client, method)(self.detail, payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.job.refresh_from_db()
            for field in self.structured:
                self.assertEqual(response.data[field], payload[field])
                self.assertEqual(getattr(self.job, field), payload[field])

    def test_optional_fields_clear_independently(self):
        for field in ('modalidade', 'cidade', 'uf'):
            response = self.client.patch(self.detail, {field: ''}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data[field], '')
        self.job.refresh_from_db()
        self.assertEqual(self.job.descricao, 'Modalidade: Remoto\n\nTexto original.')

    def test_invalid_fields_rejected_atomically_in_post_put_and_patch(self):
        invalid_values = {
            'modalidade': ['remoto', 'Hibrido', ' Remoto ', 'Outro', None],
            'cidade': ['x' * 101, '123', 'Cidade\nOutra', '<script>', None],
            'uf': ['sp', 'XX', ' SP ', 'São Paulo', None],
            'status': ['', 'Publicada', 'rascunho', ' publicada ', None],
        }
        for field, values in invalid_values.items():
            for value in values:
                for method in ('post', 'put', 'patch'):
                    with self.subTest(field=field, value=value, method=method):
                        target = self.url if method == 'post' else self.detail
                        response = getattr(self.client, method)(
                            target, {**self.base, field: value, 'titulo': 'Não salvar'}, format='json'
                        )
                        self.assertEqual(response.status_code, 400, response.data)
                        self.assertIn(field, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.titulo, self.base['titulo'])
        self.assertEqual(Freelance.objects.count(), 1)

    def test_all_modalities_and_brazilian_ufs(self):
        for field, values in [
            ('modalidade', ['Remoto', 'Híbrido', 'Presencial']),
            ('uf', [code for code, _ in Freelance.UF_CHOICES]),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.client.patch(self.detail, {field: value}, format='json')
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data[field], value)

    def test_city_normalization_and_boundaries(self):
        for value, expected in [
            ('  São Paulo  ', 'São Paulo'),
            ('Sa\u0303o Paulo', 'São Paulo'),
            ("São João d'Aliança", "São João d'Aliança"),
            ('Olho-d’Água', 'Olho-d’Água'),
            ('Sta. Maria', 'Sta. Maria'),
            ('x' * 100, 'x' * 100),
        ]:
            with self.subTest(value=value):
                response = self.client.patch(self.detail, {'cidade': value}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['cidade'], expected)

    def test_each_owner_status_transition_is_valid_and_idempotent(self):
        for previous in Freelance.Status.values:
            for following in Freelance.Status.values:
                with self.subTest(previous=previous, following=following):
                    Freelance.objects.filter(pk=self.job.pk).update(status=previous)
                    response = self.client.patch(self.detail, {'status': following}, format='json')
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['status'], following)
                    self.job.refresh_from_db()
                    self.assertEqual(self.job.status, following)

    def test_permissions_and_owner_cannot_be_transferred(self):
        for actor in (self.other, self.worker):
            self.client.force_authenticate(actor)
            for method in ('put', 'patch', 'delete'):
                response = getattr(self.client, method)(self.detail, {**self.base, **self.structured}, format='json')
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(self.url, self.base, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.detail).status_code, 401)
        self.assertEqual(self.client.post(self.url, self.base, format='json').status_code, 401)
        self.client.force_authenticate(self.company)
        response = self.client.patch(self.detail, {'status': 'cancelada', 'empresa': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['empresa'], self.company.pk)
        self.assertEqual(self.client.delete(self.detail).status_code, 204)
        self.assertFalse(Freelance.objects.filter(pk=self.job.pk).exists())

    def test_status_does_not_hide_jobs_or_change_existing_filters_and_pagination(self):
        for index in range(11):
            Freelance.objects.create(
                empresa=self.company,
                **self.base,
                tag='Web',
                tipo_contratacao='PJ',
                nivel_experiencia='Pleno',
                status='encerrada' if index % 2 else 'cancelada',
            )
        response = self.client.get(
            self.url,
            {
                'search': 'Projeto',
                'tag': 'web',
                'preco_min': '1500',
                'preco_max': '1500',
                'tipo_contratacao': 'PJ',
                'nivel_experiencia': 'Pleno',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        second = self.client.get(response.data['next'])
        self.assertEqual(len(second.data['results']), 1)
        self.assertEqual({item['status'] for item in response.data['results']}, {'encerrada', 'cancelada'})
        self.assertEqual(self.client.get(self.detail).status_code, 200)

    def test_status_keeps_applications_favorites_and_notifications_contract(self):
        self.client.force_authenticate(self.worker)
        created = self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        application = Candidatura.objects.get(pk=created.data['id'])
        favorite = Favorito.objects.create(usuario=self.worker, oportunidade=self.job)
        notification = Notificacao.objects.get(candidatura=application)
        for status in ('encerrada', 'cancelada', 'publicada'):
            self.client.force_authenticate(self.company)
            self.assertEqual(self.client.patch(self.detail, {'status': status}, format='json').status_code, 200)
            application.refresh_from_db()
            notification.refresh_from_db()
            self.assertEqual(application.status, 'pendente')
            self.assertFalse(notification.lida)
            self.assertEqual(Notificacao.objects.count(), 1)
            self.client.force_authenticate(self.worker)
            details = self.client.get(f'/api/candidaturas/{application.pk}/').data['oportunidade_detalhes']
            self.assertEqual(details['status'], status)
            favorite_data = self.client.get('/api/favoritos/').data['results'][0]
            self.assertEqual(favorite_data['id'], favorite.pk)
            self.assertEqual(favorite_data['oportunidade_detalhes']['status'], status)
        self.client.force_authenticate(self.company)
        self.client.patch(self.detail, {'status': 'encerrada'}, format='json')
        self.client.force_authenticate(self.other)
        # Existing role rules still reject companies as applicants, regardless of status.
        self.assertEqual(self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk}).status_code, 403)
        second_worker = User.objects.create_user('b47-second-worker@example.com')
        second_worker.groups.add(Group.objects.get(name='Usuário'))
        self.client.force_authenticate(second_worker)
        self.assertEqual(self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk}).status_code, 201)

    def test_openapi_exposes_structured_fields_and_preserves_required_fields(self):
        schema = SchemaGenerator(
            patterns=[
                path('api/freelances/', FreelanceViewSet.as_view({'get': 'list', 'post': 'create'})),
                path('api/freelances/<int:pk>/', FreelanceViewSet.as_view({'patch': 'partial_update'})),
            ]
        ).get_schema(public=True)
        fields = schema['components']['schemas']['Freelance']['properties']
        self.assertTrue(set(self.structured).issubset(fields))
        self.assertEqual(fields['cidade']['maxLength'], 100)
        self.assertEqual(
            set(schema['components']['schemas']['ModalidadeEnum']['enum']), set(Freelance.Modalidade.values)
        )
        self.assertEqual(
            set(schema['components']['schemas']['OpportunityStatus']['enum']), set(Freelance.Status.values)
        )
        required = schema['components']['schemas']['Freelance']['required']
        self.assertTrue({'titulo', 'preco', 'tempo'}.issubset(required))
        self.assertFalse(set(self.structured).intersection(required))


class OpportunityContractMigrationTests(TransactionTestCase):
    def test_migration_preserves_legacy_fields_owners_and_relationships(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('core', '0020_freelance_complementos')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            users = apps.get_model('core', 'User')
            company = users.objects.create(email='b47-legacy-company@example.com', password='!')
            worker = users.objects.create(email='b47-legacy-worker@example.com', password='!')
            jobs = apps.get_model('core', 'Freelance')
            job = jobs.objects.create(
                empresa=company,
                titulo='Legada',
                descricao='Modalidade: Remoto\n\nOriginal.',
                preco='25.50',
                tempo='1 dia',
                requisitos='Vue',
                beneficios='Flexível',
                tipo_contratacao='PJ',
                nivel_experiencia='Pleno',
                jornada_trabalho='20h',
                data_publicacao='2026-10-30',
                salario_minimo='10.00',
                salario_maximo='20.00',
            )
            orphan = jobs.objects.create(titulo='Sem dono', preco=0, tempo='40')
            application = apps.get_model('core', 'Candidatura').objects.create(
                freelancer=worker,
                oportunidade=job,
                status='aprovada',
            )
            favorite = apps.get_model('core', 'Favorito').objects.create(usuario=worker, oportunidade=job)
            notification = apps.get_model('core', 'Notificacao').objects.create(
                empresa=company,
                candidatura=application,
                lida=True,
            )
            snapshots = list(jobs.objects.order_by('id').values())
            MigrationExecutor(connection).migrate(latest)
            for snapshot in snapshots:
                updated = Freelance.objects.get(pk=snapshot['id'])
                for field, value in snapshot.items():
                    self.assertEqual(getattr(updated, field), value)
                for field in ('modalidade', 'cidade', 'uf'):
                    self.assertEqual(getattr(updated, field), '')
                self.assertEqual(updated.status, 'publicada')
            self.assertIsNone(Freelance.objects.get(pk=orphan.pk).empresa_id)
            self.assertEqual(Freelance.objects.get(pk=job.pk).preco, Decimal('25.50'))
            self.assertEqual(Candidatura.objects.get(pk=application.pk).status, 'aprovada')
            self.assertEqual(Favorito.objects.get(pk=favorite.pk).oportunidade_id, job.pk)
            self.assertTrue(Notificacao.objects.get(pk=notification.pk).lida)
        finally:
            MigrationExecutor(connection).migrate(latest)
