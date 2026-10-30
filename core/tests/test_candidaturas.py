# Django unittest assertions follow the existing project tests.
# ruff: noqa: PT009, PT027
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient, APITestCase

from core.models import Candidatura, Freelance, User
from core.serializers.candidatura import CandidaturaCreateSerializer


class CandidaturaTests(APITestCase):  # noqa: PLR0904 -- integration scenarios for this resource
    url = '/api/candidaturas/'

    @classmethod
    def setUpTestData(cls):
        cls.worker = User.objects.create_user(
            'candidate@example.com',
            'Secure-Candidate-41!',
            name='Candidato',
            profissao='Designer',
            habilidades=['Design', 'Python'],
            telefone='private-phone',
            localizacao='private-address',
            latitude=-26.3,
            longitude=-48.8,
            geolocation_accuracy=1,
            geolocation_timestamp=timezone.now(),
            google_id='private-google-sub',
        )
        cls.other = User.objects.create_user('other-candidate@example.com')
        cls.company = User.objects.create_user('company41@example.com')
        cls.other_company = User.objects.create_user('other-company41@example.com')
        worker_group = Group.objects.get(name='Usuário')
        company_group = Group.objects.get(name='Empresa')
        cls.worker.groups.add(worker_group)
        cls.other.groups.add(worker_group)
        cls.company.groups.add(company_group)
        cls.other_company.groups.add(company_group)
        cls.job = Freelance.objects.create(empresa=cls.company, titulo='Projeto', preco=100, tempo='Prazo livre')
        cls.other_job = Freelance.objects.create(
            empresa=cls.other_company, titulo='Outra vaga', preco=0, tempo='Sem prazo'
        )
        cls.legacy_job = Freelance.objects.create(titulo='Vaga legada', preco=0, tempo='Texto livre')

    def setUp(self):
        self.client.force_authenticate(self.worker)

    def apply(self, **data):
        return self.client.post(self.url, {'oportunidade': self.job.pk, **data}, format='json')

    def detail(self, application):
        return f'{self.url}{application.pk}/'

    def make_application(self, freelancer=None, oportunidade=None):
        return Candidatura.objects.create(freelancer=freelancer or self.worker, oportunidade=oportunidade or self.job)

    def test_create_persists_owner_status_dates_and_contract(self):
        before = timezone.now()
        response = self.apply()
        self.assertEqual(response.status_code, 201, response.data)
        application = Candidatura.objects.get(pk=response.data['id'])
        self.assertEqual(application.freelancer, self.worker)
        self.assertEqual(application.oportunidade, self.job)
        self.assertEqual(application.status, 'pendente')
        self.assertGreaterEqual(application.criado_em, before)
        self.assertGreaterEqual(application.atualizado_em, application.criado_em)
        self.assertEqual(parse_datetime(response.data['criado_em']), application.criado_em)
        self.assertEqual(parse_datetime(response.data['atualizado_em']), application.atualizado_em)
        self.assertEqual(
            set(response.data), {'id', 'freelancer', 'oportunidade', 'status', 'criado_em', 'atualizado_em'}
        )

    def test_jwt_required_and_valid_login_flow(self):
        client = APIClient()
        token = client.post(
            '/api/token/',
            {
                'email': self.worker.email,
                'password': 'Secure-Candidate-41!',
            },
            format='json',
        )
        self.assertEqual(token.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.data["access"]}')
        self.assertEqual(client.post(self.url, {'oportunidade': self.job.pk}, format='json').status_code, 201)
        self.assertEqual(client.get(self.url).data['count'], 1)
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(client.get(self.url).status_code, 401)

    def test_duplicate_returns_400_without_database_details(self):
        first = self.apply()
        second = self.apply()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data, {'oportunidade': ['Você já se candidatou a esta oportunidade.']})
        self.assertEqual(Candidatura.objects.count(), 1)

    def test_uniqueness_is_enforced_in_database(self):
        self.make_application()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_application()
        self.assertEqual(Candidatura.objects.count(), 1)

    def test_client_cannot_choose_candidate_status_or_dates(self):
        response = self.apply(
            freelancer=self.other.pk,
            status='aprovada',
            id=999999,
            criado_em='2000-01-01T00:00:00Z',
            atualizado_em='2000-01-01T00:00:00Z',
        )
        self.assertEqual(response.status_code, 201)
        application = Candidatura.objects.get()
        self.assertEqual(application.freelancer, self.worker)
        self.assertEqual(application.status, 'pendente')
        self.assertNotEqual(application.pk, 999999)
        self.assertNotEqual(application.criado_em.year, 2000)
        self.assertNotEqual(application.atualizado_em.year, 2000)

    def test_company_cannot_apply(self):
        self.client.force_authenticate(self.company)
        self.assertEqual(self.apply().status_code, 403)
        self.assertFalse(Candidatura.objects.exists())

    def test_anonymous_is_denied_on_all_endpoints(self):
        application = self.make_application()
        self.client.force_authenticate(None)
        for method, url in [('get', self.url), ('post', self.url), ('get', self.detail(application))]:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 401)

    def test_missing_or_conflicting_business_groups_are_denied(self):
        application = self.make_application()
        for groups in [[], list(Group.objects.filter(name__in=['Usuário', 'Empresa']))]:
            self.worker.groups.set(groups)
            self.assertEqual(self.apply().status_code, 403)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.get(self.detail(application)).status_code, 403)

    def test_administrative_group_does_not_grant_a_business_role(self):
        self.worker.groups.set([Group.objects.create(name='Admins only')])
        self.worker.is_staff = True
        self.worker.is_superuser = True
        self.worker.save()
        self.assertEqual(self.apply().status_code, 403)

    def test_invalid_or_missing_opportunity(self):
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 400)
        for opportunity in [None, 'invalid', {}, [], True, -1, 0, 1.5, 999999, 2**64]:
            with self.subTest(opportunity=opportunity):
                response = self.apply(oportunidade=opportunity)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('oportunidade', response.data)
        self.assertFalse(Candidatura.objects.exists())

    def test_existing_opportunities_have_no_invented_availability_rules(self):
        for job in [self.job, self.other_job, self.legacy_job]:
            self.assertEqual(self.apply(oportunidade=job.pk).status_code, 201)

    def test_list_and_detail_are_own_only(self):
        own = self.make_application()
        hidden = self.make_application(freelancer=self.other)
        response = self.client.get(self.url, {'freelancer': self.other.pk, 'empresa': self.other_company.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.pk)
        detail = self.client.get(self.detail(own))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['oportunidade_detalhes']['titulo'], self.job.titulo)
        self.assertEqual(detail.data['status'], 'pendente')
        self.assertEqual(self.client.get(self.detail(hidden)).status_code, 404)
        self.assertEqual(self.client.get(f'{self.url}999999/').status_code, 404)

    def test_newest_first_and_pagination(self):
        applications = []
        for index in range(11):
            job = Freelance.objects.create(empresa=self.company, titulo=f'Vaga {index}', preco=1, tempo='1 dia')
            applications.append(self.make_application(oportunidade=job))
        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['results'][0]['id'], applications[-1].pk)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(self.client.get(self.url, {'page': 2}).data['results'][0]['id'], applications[0].pk)

    def test_current_status_and_dates_can_be_read_without_mutation(self):
        application = self.make_application()
        for status in Candidatura.Status.values:
            # Future operational transitions are not exposed by any HTTP endpoint.
            application.status = status
            application.save()
            response = self.client.get(self.detail(application))
            self.assertEqual(response.data['status'], status)
            self.assertEqual(parse_datetime(response.data['atualizado_em']), application.atualizado_em)

    def test_company_only_reads_candidates_for_own_opportunities(self):
        own = self.make_application()
        hidden = self.make_application(oportunidade=self.other_job)
        self.client.force_authenticate(self.company)
        response = self.client.get(self.url, {'empresa': self.other_company.pk})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.pk)
        self.assertEqual(self.client.get(self.detail(own)).status_code, 200)
        self.assertEqual(self.client.get(self.detail(hidden)).status_code, 404)

    def test_opportunity_filter_respects_role_and_property(self):
        own = self.make_application()
        self.make_application(oportunidade=self.other_job)
        self.make_application(freelancer=self.other)
        response = self.client.get(self.url, {'oportunidade': self.job.pk})
        self.assertEqual([item['id'] for item in response.data['results']], [own.pk])
        self.client.force_authenticate(self.company)
        self.assertEqual(self.client.get(self.url, {'oportunidade': self.job.pk}).data['count'], 2)
        self.assertEqual(self.client.get(self.url, {'oportunidade': self.other_job.pk}).data['count'], 0)
        self.assertEqual(self.client.get(self.url, {'oportunidade': 999999}).data['count'], 0)
        for value in ['invalid', '-1', '', '1.5', str(2**64)]:
            self.assertEqual(self.client.get(self.url, {'oportunidade': value}).status_code, 400)

    def test_candidate_projection_excludes_private_fields_and_values(self):
        application = self.make_application()
        self.client.force_authenticate(self.company)
        response = self.client.get(self.detail(application))
        candidate = response.data['freelancer_detalhes']
        self.assertEqual(set(candidate), {'id', 'name', 'profissao', 'habilidades', 'profile_image'})
        self.assertEqual(candidate['id'], self.worker.pk)
        self.assertEqual(candidate['name'], 'Candidato')
        self.assertEqual(candidate['habilidades'], ['Design', 'Python'])
        for value in [
            self.worker.email,
            'private-phone',
            'private-address',
            'private-google-sub',
            self.worker.password,
        ]:
            self.assertNotIn(value, str(response.data))

    def test_no_company_gains_access_to_ownerless_opportunity(self):
        application = self.make_application(oportunidade=self.legacy_job)
        for company in [self.company, self.other_company]:
            self.client.force_authenticate(company)
            self.assertEqual(self.client.get(self.detail(application)).status_code, 404)
            self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.client.force_authenticate(self.worker)
        self.assertEqual(self.client.get(self.detail(application)).status_code, 200)

    def test_updates_deletion_and_decision_actions_are_unavailable(self):
        application = self.make_application()
        for actor in [self.worker, self.company]:
            self.client.force_authenticate(actor)
            for method in ['put', 'patch', 'delete']:
                for status in ['aprovada', 'recusada']:
                    response = getattr(self.client, method)(
                        self.detail(application),
                        {
                            'status': status,
                            'freelancer': self.other.pk,
                            'oportunidade': self.other_job.pk,
                        },
                        format='json',
                    )
                    self.assertEqual(response.status_code, 405)
            for action in ['aprovar', 'recusar']:
                self.assertEqual(self.client.post(f'{self.detail(application)}{action}/').status_code, 404)
        application.refresh_from_db()
        self.assertEqual(application.status, 'pendente')
        self.assertEqual(application.freelancer, self.worker)
        self.assertEqual(application.oportunidade, self.job)

    def test_listing_uses_related_objects_without_per_candidate_queries(self):
        for index in range(10):
            worker = User.objects.create_user(f'candidate-query-{index}@example.com')
            self.make_application(freelancer=worker)
        self.client.force_authenticate(self.company)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 10)
        self.assertLessEqual(len(queries), 6)

    def test_deletion_relationships_preserve_existing_opportunity_contract(self):
        application = self.make_application()
        self.company.delete()
        self.job.refresh_from_db()
        self.assertIsNone(self.job.empresa_id)
        self.assertTrue(Candidatura.objects.filter(pk=application.pk).exists())
        self.job.delete()
        self.assertFalse(Candidatura.objects.filter(pk=application.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.worker.pk).exists())
        self.make_application(oportunidade=self.other_job)
        self.worker.delete()
        self.assertFalse(Candidatura.objects.exists())
        self.assertTrue(Freelance.objects.filter(pk=self.other_job.pk).exists())

    def test_operational_database_error_returns_generic_503(self):
        with patch(
            'core.serializers.candidatura.Candidatura.objects.create', side_effect=OperationalError('private SQL')
        ):
            response = self.apply()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private SQL', str(response.data))
        self.assertFalse(Candidatura.objects.exists())


class CandidaturaConcurrencyTests(TransactionTestCase):
    def test_simultaneous_requests_cannot_create_duplicate_applications(self):
        worker = User.objects.create_user('concurrent-candidate@example.com')
        group, _ = Group.objects.get_or_create(name='Usuário')
        worker.groups.add(group)
        job = Freelance.objects.create(titulo='Concorrente', preco=1, tempo='1 dia')
        barrier = Barrier(2)
        original_create = CandidaturaCreateSerializer.create

        def synchronized_create(serializer, validated_data):
            barrier.wait(timeout=10)
            return original_create(serializer, validated_data)

        def submit(_):
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=worker.pk))
                return client.post('/api/candidaturas/', {'oportunidade': job.pk}, format='json').status_code
            finally:
                connections.close_all()

        with (
            patch.object(CandidaturaCreateSerializer, 'create', synchronized_create),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            statuses = list(pool.map(submit, range(2)))
        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertTrue(all(status in {201, 400, 503} for status in statuses), statuses)
        self.assertEqual(Candidatura.objects.filter(freelancer=worker, oportunidade=job).count(), 1)
        # SQLite may reject a simultaneous writer temporarily; a retry must be a duplicate, never a second row.
        client = APIClient()
        client.force_authenticate(worker)
        self.assertEqual(client.post('/api/candidaturas/', {'oportunidade': job.pk}, format='json').status_code, 400)
