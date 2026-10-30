# Django integration assertions retain response diagnostics.
# ruff: noqa: PT009, PT027
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Group
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Candidatura, Freelance, Notificacao, User
from core.serializers.candidatura import CandidaturaCreateSerializer
from core.whatsapp import normalizar_telefone


class NotificacaoTests(APITestCase):  # noqa: PLR0904 -- API integration scenarios
    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('company44@example.com', name='Empresa & Cia')
        cls.other_company = User.objects.create_user('other44@example.com')
        cls.worker = User.objects.create_user(
            'worker44@example.com',
            'private-password',
            name='João & Maria',
            telefone='(47) 99999-9999',
            profissao='Designer',
            habilidades=['Design'],
            profile_image='users/test.jpg',
            google_id='private-google',
            latitude=-26,
            longitude=-48,
            localizacao='private-location',
        )
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.other_company.groups.add(Group.objects.get(name='Empresa'))
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.job = Freelance.objects.create(empresa=cls.company, titulo='Design & UX', preco=100, tempo='1 dia')
        cls.other_job = Freelance.objects.create(empresa=cls.other_company, titulo='Outra', preco=1, tempo='1 dia')

    def setUp(self):
        self.client.force_authenticate(self.worker)

    def apply(self, job=None):
        response = self.client.post('/api/candidaturas/', {'oportunidade': (job or self.job).pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Candidatura.objects.get(pk=response.data['id'])

    def decide(self, application, action='aprovar', **kwargs):
        return self.client.post(f'/api/candidaturas/{application.pk}/{action}/', **kwargs)

    def test_application_creates_one_unread_notification_with_live_relations(self):
        application = self.apply()
        notification = Notificacao.objects.get()
        self.assertEqual(notification.candidatura, application)
        self.assertEqual(notification.empresa, self.company)
        self.assertFalse(notification.lida)
        self.assertGreaterEqual(notification.criado_em, application.criado_em)
        self.client.force_authenticate(self.company)
        response = self.client.get('/api/notificacoes/')
        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertEqual(item['candidatura'], application.pk)
        self.assertEqual(item['freelancer'], self.worker.pk)
        self.assertEqual(item['freelancer_detalhes']['name'], self.worker.name)
        self.assertEqual(item['freelancer_detalhes']['profissao'], 'Designer')
        self.assertIn('/media/users/test.jpg', item['freelancer_detalhes']['profile_image'])
        self.assertEqual(item['oportunidade'], self.job.pk)
        self.assertEqual(item['oportunidade_titulo'], self.job.titulo)
        self.assertEqual(item['status'], 'pendente')
        self.assertEqual(
            set(item),
            {
                'id',
                'candidatura',
                'freelancer',
                'freelancer_detalhes',
                'oportunidade',
                'oportunidade_titulo',
                'status',
                'candidatura_criado_em',
                'criado_em',
                'lida',
            },
        )

    def test_duplicate_application_and_notification_database_constraint(self):
        application = self.apply()
        duplicate = self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk})
        self.assertEqual(duplicate.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notificacao.objects.create(candidatura=application, empresa=self.company)
        self.assertEqual(Candidatura.objects.count(), 1)
        self.assertEqual(Notificacao.objects.count(), 1)

    def test_notification_failure_rolls_back_entire_application(self):
        for failure, expected in [(IntegrityError('private SQL'), 400), (OperationalError('private SQL'), 503)]:
            with (
                self.subTest(failure=failure),
                patch('core.views.candidatura.Notificacao.objects.get_or_create', side_effect=failure),
            ):
                response = self.client.post('/api/candidaturas/', {'oportunidade': self.job.pk})
                self.assertEqual(response.status_code, expected)
                self.assertNotIn('private SQL', str(response.data))
                self.assertFalse(Candidatura.objects.exists())
                self.assertFalse(Notificacao.objects.exists())

    def test_ownerless_legacy_opportunity_keeps_application_without_inventing_recipient(self):
        job = Freelance.objects.create(titulo='Legada', preco=1, tempo='1 dia')
        application = self.apply(job)
        self.assertFalse(Notificacao.objects.exists())
        self.client.force_authenticate(self.company)
        self.assertEqual(self.decide(application).status_code, 404)

    def test_company_sees_only_own_list_detail_and_read_action(self):
        own = self.apply().notificacao
        hidden = self.apply(self.other_job).notificacao
        self.client.force_authenticate(self.company)
        response = self.client.get('/api/notificacoes/', {'empresa': self.other_company.pk})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.pk)
        self.assertEqual(self.client.get(f'/api/notificacoes/{own.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/notificacoes/{hidden.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/notificacoes/{hidden.pk}/marcar-lida/').status_code, 404)
        hidden.refresh_from_db()
        self.assertFalse(hidden.lida)

    def test_notifications_require_company_role_and_jwt(self):
        notification = self.apply().notificacao
        routes = [
            ('get', '/api/notificacoes/'),
            ('get', f'/api/notificacoes/{notification.pk}/'),
            ('patch', f'/api/notificacoes/{notification.pk}/marcar-lida/'),
        ]
        for actor in [self.worker, None]:
            self.client.force_authenticate(actor)
            for method, route in routes:
                with self.subTest(actor=actor, method=method):
                    self.assertEqual(getattr(self.client, method)(route).status_code, 403 if actor else 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.company).access_token}')
        self.assertEqual(self.client.get('/api/notificacoes/').status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get('/api/notificacoes/').status_code, 401)

    def test_ambiguous_and_missing_roles_do_not_gain_access_even_as_admin(self):
        application = self.apply()
        self.company.is_staff = self.company.is_superuser = True
        self.company.save()
        for groups in [[], list(Group.objects.filter(name__in=['Empresa', 'Usuário']))]:
            self.company.groups.set(groups)
            self.client.force_authenticate(self.company)
            self.assertEqual(self.client.get('/api/notificacoes/').status_code, 403)
            self.assertEqual(self.decide(application).status_code, 403)

    def test_mark_read_is_idempotent_and_cannot_modify_other_fields(self):
        application = self.apply()
        notification = application.notificacao
        self.client.force_authenticate(self.company)
        url = f'/api/notificacoes/{notification.pk}/marcar-lida/'
        payload = {'lida': False, 'empresa': self.other_company.pk, 'candidatura': 999, 'status': 'aprovada'}
        first = self.client.patch(url, payload, format='json')
        second = self.client.patch(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data, second.data)
        notification.refresh_from_db()
        application.refresh_from_db()
        self.assertTrue(notification.lida)
        self.assertEqual(notification.empresa, self.company)
        self.assertEqual(notification.candidatura, application)
        self.assertEqual(application.status, 'pendente')

    def test_filters_combine_and_track_current_status(self):
        pending = self.apply()
        approved = self.apply(self.other_job)
        self.other_job.empresa = self.company
        self.other_job.save()
        Notificacao.objects.filter(candidatura=approved).update(empresa=self.company, lida=True)
        approved.status = 'aprovada'
        approved.save()
        self.client.force_authenticate(self.company)
        for params, ids in [
            ({'lida': 'false'}, [pending.notificacao.pk]),
            ({'lida': 'true', 'status': 'aprovada'}, [approved.notificacao.pk]),
            ({'status': 'pendente'}, [pending.notificacao.pk]),
            ({'status': 'recusada'}, []),
            ({'lida': 'false', 'status': 'aprovada'}, []),
        ]:
            with self.subTest(params=params):
                response = self.client.get('/api/notificacoes/', params)
                self.assertEqual([item['id'] for item in response.data['results']], ids)
        for params in [{'status': 'unknown'}, {'status': ''}, {'lida': 'unknown'}, {'lida': ''}]:
            self.assertEqual(self.client.get('/api/notificacoes/', params).status_code, 400)

    def test_pagination_and_bounded_query_count(self):
        for index in range(11):
            job = Freelance.objects.create(empresa=self.company, titulo=f'Vaga {index}', preco=1, tempo='1 dia')
            self.apply(job)
        self.client.force_authenticate(self.company)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/notificacoes/')
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        self.assertLessEqual(len(queries), 4)
        self.assertIsNotNone(response.data['next'])
        second = self.client.get('/api/notificacoes/', {'page': 2})
        self.assertEqual(len(second.data['results']), 1)
        self.assertGreater(response.data['results'][0]['id'], second.data['results'][0]['id'])
        self.assertEqual(self.client.get('/api/notificacoes/', {'page': 3}).status_code, 404)

    def test_approval_persists_timestamp_and_exposes_encoded_manual_contact(self):
        application = self.apply()
        old_time = application.atualizado_em
        self.client.force_authenticate(self.company)
        response = self.decide(application, data={'status': 'recusada', 'freelancer': self.other_company.pk})
        self.assertEqual(response.status_code, 200, response.data)
        application.refresh_from_db()
        self.assertEqual(application.status, 'aprovada')
        self.assertGreater(application.atualizado_em, old_time)
        self.assertEqual(application.freelancer, self.worker)
        contact = response.data['whatsapp']
        self.assertTrue(contact['disponivel'])
        self.assertFalse(contact['mensagem_enviada'])
        parsed = urlparse(contact['url'])
        self.assertEqual(parsed.netloc, 'wa.me')
        self.assertEqual(parsed.path, '/5547999999999')
        self.assertEqual(
            parse_qs(parsed.query)['text'],
            [
                'Olá, João & Maria! Sua candidatura para a vaga Design & UX foi aprovada pela empresa '
                'Empresa & Cia através do MaRuJoBs. Gostaríamos de conversar com você sobre os próximos passos.'
            ],
        )
        self.assertEqual(self.client.get(f'/api/candidaturas/{application.pk}/').data, response.data)
        notification = self.client.get(f'/api/notificacoes/{application.notificacao.pk}/')
        self.assertEqual(notification.data['status'], 'aprovada')

    def test_refusal_persists_and_does_not_expose_contact(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        response = self.decide(application, 'recusar')
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, 'recusada')
        self.assertFalse(response.data['whatsapp']['disponivel'])
        self.assertIsNone(response.data['whatsapp']['url'])

    def test_other_company_and_freelancer_cannot_decide(self):
        application = self.apply()
        for actor, expected in [(self.worker, 403), (self.other_company, 404), (None, 401)]:
            self.client.force_authenticate(actor)
            for action in ['aprovar', 'recusar']:
                self.assertEqual(self.decide(application, action).status_code, expected)
        application.refresh_from_db()
        self.assertEqual(application.status, 'pendente')

    def test_same_decision_is_idempotent_and_opposite_returns_409(self):
        for decision, opposite in [('aprovar', 'recusar'), ('recusar', 'aprovar')]:
            application = self.apply(self.job if decision == 'aprovar' else self.other_job)
            self.client.force_authenticate(self.company if decision == 'aprovar' else self.other_company)
            first = self.decide(application, decision)
            self.assertEqual(first.status_code, 200)
            second = self.decide(application, decision)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.data, second.data)
            self.assertEqual(self.decide(application, opposite).status_code, 409)
            application.refresh_from_db()
            self.assertEqual(application.status, first.data['status'])
            self.assertEqual(Notificacao.objects.filter(candidatura=application).count(), 1)
            self.client.force_authenticate(self.worker)

    def test_contact_before_approval_invalid_phone_and_freelancer_visibility(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        url = f'/api/candidaturas/{application.pk}/'
        pending = self.client.get(url).data
        self.assertFalse(pending['whatsapp']['disponivel'])
        self.assertIsNone(pending['whatsapp']['url'])
        self.worker.telefone = 'invalid-phone'
        self.worker.save()
        response = self.decide(application)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['whatsapp']['motivo'], 'telefone_invalido')
        self.assertIsNone(response.data['whatsapp']['url'])
        self.worker.telefone = '+55 47 99999-9999'
        self.worker.save()
        self.assertTrue(self.client.get(url).data['whatsapp']['disponivel'])
        self.client.force_authenticate(self.worker)
        for response in [self.client.get(url), self.client.get('/api/candidaturas/')]:
            self.assertNotIn('whatsapp', str(response.data))
            self.assertNotIn('wa.me', str(response.data))
            self.assertNotIn('5547999999999', str(response.data))

    def test_professional_data_only_and_no_public_whatsapp(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        responses = [self.client.get('/api/notificacoes/'), self.client.get(f'/api/candidaturas/{application.pk}/')]
        for response in responses:
            text = str(response.data)
            for private in [
                self.worker.email,
                self.worker.password,
                self.worker.google_id,
                'private-location',
                'latitude',
                'longitude',
                'geolocation',
                'is_staff',
                'is_superuser',
                'permissions',
                'telefone',
                'password',
                'token',
            ]:
                self.assertNotIn(private, text)
        self.decide(application)
        for response in [self.client.get('/api/freelances/'), self.client.get(f'/api/freelances/{self.job.pk}/')]:
            self.assertNotIn('wa.me', str(response.data))
            self.assertNotIn('telefone', str(response.data))

    def test_generic_writes_remain_disabled_for_both_resources(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        for method in ['put', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)(f'/api/candidaturas/{application.pk}/').status_code, 405)
        for method in ['post', 'put', 'patch', 'delete']:
            url = '/api/notificacoes/' if method == 'post' else f'/api/notificacoes/{application.notificacao.pk}/'
            self.assertEqual(getattr(self.client, method)(url).status_code, 405)

    def test_contact_and_notifications_hidden_after_loss_of_ownership(self):
        application = self.apply()
        self.job.empresa = self.other_company
        self.job.save()
        self.client.force_authenticate(self.company)
        self.assertEqual(self.client.get('/api/notificacoes/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/notificacoes/{application.notificacao.pk}/').status_code, 404)
        self.assertEqual(self.decide(application).status_code, 404)

    def test_decision_lock_error_returns_safe_503_and_keeps_pending(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        with patch('django.db.models.query.QuerySet.select_for_update', side_effect=OperationalError('secret SQL')):
            response = self.decide(application)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret SQL', str(response.data))
        application.refresh_from_db()
        self.assertEqual(application.status, 'pendente')

    def test_decision_ignores_list_filters_and_missing_ids_return_404(self):
        application = self.apply()
        self.client.force_authenticate(self.company)
        response = self.client.post(f'/api/candidaturas/{application.pk}/aprovar/?status=pendente')
        self.assertEqual(response.status_code, 200)
        for pk in ['999999', 'invalid']:
            self.assertEqual(self.client.post(f'/api/candidaturas/{pk}/aprovar/').status_code, 404)


class TelefoneTests(SimpleTestCase):
    def test_safe_normalization_of_brazilian_and_explicit_international_numbers(self):
        for raw, normalized in [
            ('(47) 99999-9999', '5547999999999'),
            ('+55 (47) 99999-9999', '5547999999999'),
            ('5547999999999', '5547999999999'),
            ('(11) 3456-7890', '551134567890'),
            ('+44 20 8366 1177', '442083661177'),
            ('+1 650 253 2222', '16502532222'),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalizar_telefone(raw), normalized)

    def test_invalid_or_ambiguous_numbers_are_not_repaired(self):
        for raw in [
            None,
            '',
            '99999-9999',
            '4799999999',
            '00000000000',
            '+999123456789',
            '+55119999',
            '047999999999',
            '005547999999999',
            '1 650 253 2222',
            'call +5547999999999',
            '+5547999999999 ramal 12',
            '+55 (047) 99999-9999',
            '１２３４５６７８９０',
            '11 1234-5678',
        ]:
            with self.subTest(raw=raw):
                self.assertIsNone(normalizar_telefone(raw))


class DecisaoConcurrencyTests(TransactionTestCase):
    def test_simultaneous_opposite_decisions_never_overwrite_the_winner(self):
        company = User.objects.create_user('concurrent44@example.com')
        group, _ = Group.objects.get_or_create(name='Empresa')
        company.groups.add(group)
        worker = User.objects.create_user('concurrent-worker44@example.com')
        job = Freelance.objects.create(empresa=company, titulo='Concorrência', preco=1, tempo='1 dia')
        application = Candidatura.objects.create(freelancer=worker, oportunidade=job)
        notification = Notificacao.objects.create(candidatura=application, empresa=company)
        barrier = Barrier(2)
        original = Candidatura.objects.all().__class__.select_for_update

        def synchronized_lock(queryset, *args, **kwargs):
            barrier.wait(timeout=10)
            return original(queryset, *args, **kwargs)

        def submit(action):
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=company.pk))
                response = client.post(f'/api/candidaturas/{application.pk}/{action}/')
                return action, response.status_code
            finally:
                connections.close_all()

        with (
            patch('django.db.models.query.QuerySet.select_for_update', synchronized_lock),
            ThreadPoolExecutor(2) as pool,
        ):
            outcomes = list(pool.map(submit, ['aprovar', 'recusar']))
        self.assertTrue(all(status in {200, 409, 503} for _, status in outcomes), outcomes)
        winners = [action for action, status in outcomes if status == http_status.HTTP_200_OK]
        self.assertLessEqual(len(winners), 1, outcomes)
        # SQLite may reject a contending writer with 503; retry after both transactions end.
        client = APIClient()
        client.force_authenticate(company)
        if not winners:
            self.assertEqual(client.post(f'/api/candidaturas/{application.pk}/aprovar/').status_code, 200)
            winners = ['aprovar']
        winner = winners[0]
        opposite = 'recusar' if winner == 'aprovar' else 'aprovar'
        application.refresh_from_db()
        saved_time = application.atualizado_em
        self.assertEqual(application.status, 'aprovada' if winner == 'aprovar' else 'recusada')
        self.assertEqual(client.post(f'/api/candidaturas/{application.pk}/{opposite}/').status_code, 409)
        self.assertEqual(client.post(f'/api/candidaturas/{application.pk}/{winner}/').status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.atualizado_em, saved_time)
        self.assertEqual(Notificacao.objects.get(candidatura=application).pk, notification.pk)


class NotificacaoCreationConcurrencyTests(TransactionTestCase):
    def test_simultaneous_applications_create_exactly_one_application_and_notification(self):
        worker = User.objects.create_user('notification-race44@example.com')
        group, _ = Group.objects.get_or_create(name='Usuário')
        worker.groups.add(group)
        company = User.objects.create_user('notification-company-race44@example.com')
        job = Freelance.objects.create(empresa=company, titulo='Vaga', preco=1, tempo='1 dia')
        barrier = Barrier(2)
        original_create = CandidaturaCreateSerializer.create

        def synchronized_create(serializer, validated_data):
            barrier.wait(timeout=10)
            return original_create(serializer, validated_data)

        def submit(_):
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=worker.pk))
                return client.post('/api/candidaturas/', {'oportunidade': job.pk}).status_code
            finally:
                connections.close_all()

        with (
            patch.object(CandidaturaCreateSerializer, 'create', synchronized_create),
            ThreadPoolExecutor(2) as pool,
        ):
            statuses = list(pool.map(submit, range(2)))
        self.assertTrue(all(status in {201, 400, 503} for status in statuses), statuses)
        # Retry transient lock contention after both competing transactions have finished.
        client = APIClient()
        client.force_authenticate(worker)
        retry = client.post('/api/candidaturas/', {'oportunidade': job.pk})
        self.assertIn(retry.status_code, {201, 400})
        self.assertEqual(Candidatura.objects.filter(freelancer=worker, oportunidade=job).count(), 1)
        notification = Notificacao.objects.get()
        self.assertEqual(notification.candidatura.freelancer, worker)
        self.assertEqual(notification.empresa, company)


class NotificacaoMigrationTests(TransactionTestCase):
    def test_backfill_preserves_existing_data_read_state_and_uniqueness(self):  # noqa: PLR0914
        executor = MigrationExecutor(connection)
        executor.migrate([('core', '0017_candidatura')])
        try:
            old_apps = executor.loader.project_state([('core', '0017_candidatura')]).apps
            user_model = old_apps.get_model('core', 'User')
            job_model = old_apps.get_model('core', 'Freelance')
            application_model = old_apps.get_model('core', 'Candidatura')
            company = user_model.objects.create(email='legacy-company44@example.com', password='!')
            worker = user_model.objects.create(email='legacy-worker44@example.com', password='!')
            job = job_model.objects.create(empresa=company, titulo='Legada', preco=1, tempo='1 dia')
            orphan = job_model.objects.create(titulo='Sem empresa', preco=1, tempo='1 dia')
            applications = []
            for status in ['pendente', 'aprovada', 'recusada']:
                candidate = user_model.objects.create(email=f'legacy-{status}44@example.com', password='!')
                applications.append(
                    application_model.objects.create(freelancer=candidate, oportunidade=job, status=status)
                )
            orphan_application = application_model.objects.create(freelancer=worker, oportunidade=orphan)
            snapshots = list(application_model.objects.order_by('pk').values())
            executor = MigrationExecutor(connection)
            executor.migrate([('core', '0018_notificacao')])
            apps = executor.loader.project_state([('core', '0018_notificacao')]).apps
            notification_model = apps.get_model('core', 'Notificacao')
            existing = notification_model.objects.create(
                empresa_id=company.pk, candidatura_id=applications[0].pk, lida=True
            )
            executor = MigrationExecutor(connection)
            executor.migrate([('core', '0019_notificacoes_retroativas')])
            existing.refresh_from_db()
            self.assertTrue(existing.lida)
            self.assertEqual(notification_model.objects.count(), 3)
            self.assertFalse(notification_model.objects.filter(candidatura_id=orphan_application.pk).exists())
            self.assertEqual(list(application_model.objects.order_by('pk').values()), snapshots)
            migration = import_module('core.migrations.0019_notificacoes_retroativas')
            with connection.schema_editor() as editor:
                migration.criar_notificacoes_retroativas(apps, editor)
            self.assertEqual(notification_model.objects.count(), 3)
            existing.refresh_from_db()
            self.assertTrue(existing.lida)
        finally:
            MigrationExecutor(connection).migrate([('core', '0019_notificacoes_retroativas')])
