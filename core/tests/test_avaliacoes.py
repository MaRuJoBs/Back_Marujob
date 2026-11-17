# Match the Django assertion style used by the existing API tests.
# ruff: noqa: PT009, PT027
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Avaliacao, Candidatura, ConclusaoTrabalho, Freelance, User


class TrabalhoFixture:
    def setUp(self):
        super().setUp()
        empresa, _ = Group.objects.get_or_create(name='Empresa')
        usuario, _ = Group.objects.get_or_create(name='Usuário')
        self.company = User.objects.create_user('company57@example.com', 'private-password', name='Empresa')
        self.other_company = User.objects.create_user('other-company57@example.com')
        self.worker = User.objects.create_user(
            'worker57@example.com',
            'private-password',
            name='Freelancer',
            perfil_publico=True,
            telefone='private-phone',
            google_id='private-google-id',
            localizacao='private-address',
            latitude=-26,
            longitude=-48,
        )
        self.outsider = User.objects.create_user('outsider57@example.com', perfil_publico=True)
        self.company.groups.add(empresa)
        self.other_company.groups.add(empresa)
        self.worker.groups.add(usuario)
        self.outsider.groups.add(usuario)
        self.job = Freelance.objects.create(empresa=self.company, titulo='Trabalho', preco=100, tempo='1 dia')
        response = self.api(self.worker).post('/api/candidaturas/', {'oportunidade': self.job.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Candidatura.objects.get(pk=response.data['id'])

    @staticmethod
    def api(user=None):
        client = APIClient()
        if user is not None:
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        return client

    def completion_url(self, application=None):
        return f'/api/candidaturas/{(application or self.application).pk}/conclusao/'

    def approve(self, application=None):
        application = application or self.application
        result = self.api(self.company).post(f'/api/candidaturas/{application.pk}/aprovar/', {}, format='json')
        self.assertEqual(result.status_code, 200, result.data)

    def confirm(self, user, application=None, **payload):
        return self.api(user).post(self.completion_url(application), payload, format='json')

    def finish(self, application=None, first=None):
        application = application or self.application
        self.approve(application)
        first = first or self.company
        second = self.worker if first == self.company else self.company
        a = self.confirm(first, application)
        self.assertEqual(a.status_code, 200, a.data)
        self.assertFalse(a.data['concluido'])
        b = self.confirm(second, application)
        self.assertEqual(b.status_code, 200, b.data)
        self.assertTrue(b.data['concluido'])

    def review(self, user=None, application=None, **payload):
        return self.api(user or self.company).post(
            '/api/avaliacoes/',
            {'candidatura_id': (application or self.application).pk, 'nota': 5, **payload},
            format='json',
        )

    def reputation(self, user=None):
        user = user or self.worker
        return self.api(self.company).get(f'/api/avaliacoes/usuarios/{user.pk}/reputacao/')


class AvaliacaoTests(TrabalhoFixture, APITestCase):  # noqa: PLR0904
    def test_both_parties_review_only_after_real_api_confirmations(self):
        self.finish()
        company = self.review(comentario='Entregou o combinado.')
        worker = self.review(self.worker, nota=4, comentario='Boa comunicação.')
        self.assertEqual(company.status_code, 201, company.data)
        self.assertEqual(worker.status_code, 201, worker.data)
        self.assertEqual(company.data['avaliador'], self.company.pk)
        self.assertEqual(company.data['avaliado'], self.worker.pk)
        self.assertEqual(worker.data['avaliador'], self.worker.pk)
        self.assertEqual(worker.data['avaliado'], self.company.pk)
        self.assertEqual(Avaliacao.objects.validas().count(), 2)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'aprovada')

    def test_pending_and_rejected_applications_do_not_allow_completion_or_reviews(self):
        for state in ['pendente', 'recusada']:
            Candidatura.objects.filter(pk=self.application.pk).update(status=state)
            for user in [self.worker, self.company]:
                with self.subTest(state=state, user=user.pk):
                    self.assertEqual(self.confirm(user).status_code, 409)
                    self.assertEqual(self.review(user).status_code, 409)
        self.assertFalse(ConclusaoTrabalho.objects.exists())
        self.assertFalse(Avaliacao.objects.exists())

    def test_approval_and_closed_or_cancelled_job_are_not_completion(self):
        self.approve()
        for state in ['publicada', 'encerrada', 'cancelada']:
            Freelance.objects.filter(pk=self.job.pk).update(status=state)
            self.assertEqual(self.review().status_code, 409)
        self.assertFalse(ConclusaoTrabalho.objects.exists())

    def test_one_confirmation_is_insufficient_in_either_order(self):
        self.approve()
        for user in [self.company, self.worker]:
            ConclusaoTrabalho.objects.all().delete()
            self.assertEqual(self.confirm(user).status_code, 200)
            for reviewer in [self.company, self.worker]:
                self.assertEqual(self.review(reviewer).status_code, 409)
        self.assertFalse(Avaliacao.objects.exists())

    def test_worker_can_confirm_first_and_retries_preserve_original_dates(self):
        self.finish(first=self.worker)
        before = ConclusaoTrabalho.objects.values().get()
        for user in [self.company, self.worker]:
            response = self.confirm(user)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['concluido'])
        self.assertEqual(ConclusaoTrabalho.objects.values().get(), before)

    def test_get_completion_does_not_create_evidence(self):
        response = self.api(self.worker).get(self.completion_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                'candidatura_id': self.application.pk,
                'empresa_confirmou_em': None,
                'freelancer_confirmou_em': None,
                'concluido': False,
            },
        )
        self.assertFalse(ConclusaoTrabalho.objects.exists())

    def test_nonparticipants_cannot_confirm_view_or_review(self):
        self.finish()
        for user in [self.outsider, self.other_company]:
            self.assertEqual(self.confirm(user).status_code, 404)
            self.assertEqual(self.api(user).get(self.completion_url()).status_code, 404)
            self.assertEqual(self.review(user).status_code, 404)
        self.assertFalse(Avaliacao.objects.exists())

    def test_self_relationship_and_ownerless_legacy_job_fail_closed(self):
        self.approve()
        for owner in [self.worker, None]:
            Freelance.objects.filter(pk=self.job.pk).update(empresa=owner)
            self.assertEqual(self.confirm(self.worker).status_code, 409)
            self.assertEqual(self.review(self.worker).status_code, 409)
        self.assertFalse(ConclusaoTrabalho.objects.exists())

    def test_payload_cannot_forge_completion_identity_dates_or_other_party(self):
        self.approve()
        for payload in [
            {'empresa_id': self.company.pk},
            {'freelancer_confirmou_em': '2026-01-01T00:00:00Z'},
            {'concluido': True},
            {'avaliador': self.worker.pk},
        ]:
            self.assertEqual(self.confirm(self.worker, **payload).status_code, 400)
        self.assertFalse(ConclusaoTrabalho.objects.exists())
        self.finish()
        for field in ['avaliador', 'avaliado', 'avaliador_id', 'avaliado_id', 'criado_em', 'id']:
            self.assertEqual(self.review(**{field: self.outsider.pk}).status_code, 400)
        self.assertFalse(Avaliacao.objects.exists())

    def test_duplicate_is_conflict_and_original_stays_unchanged(self):
        self.finish()
        first = self.review(nota=3, comentario='Original')
        self.assertEqual(first.status_code, 201)
        duplicate = self.review(nota=1, comentario='Mudou')
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(Avaliacao.objects.get().nota, 3)
        self.assertEqual(Avaliacao.objects.get().comentario, 'Original')

    def test_each_work_allows_one_rating_per_author(self):
        self.finish()
        self.assertEqual(self.review().status_code, 201)
        result = self.api(self.worker).post(
            '/api/candidaturas/', {'oportunidade': self._second_job().pk}, format='json'
        )
        second = Candidatura.objects.get(pk=result.data['id'])
        self.finish(second)
        self.assertEqual(self.review(application=second, nota=3).status_code, 201)
        self.assertEqual(Avaliacao.objects.count(), 2)

    def _second_job(self):
        return Freelance.objects.create(empresa=self.company, titulo='Outro trabalho', preco=10, tempo='1 dia')

    def test_invalid_scores_required_fields_and_comment_limit(self):
        self.finish()
        for score in [0, -1, 6, 100, 1.5, 1.0, True, False, None, 'abc', [], {}]:
            with self.subTest(score=score):
                self.assertEqual(self.review(nota=score).status_code, 400)
        for body in [{}, {'candidatura_id': self.application.pk}, {'nota': 3}, [], {'candidatura_id': True, 'nota': 3}]:
            self.assertEqual(self.api(self.company).post('/api/avaliacoes/', body, format='json').status_code, 400)
        self.assertEqual(self.review(comentario='a' * 1001).status_code, 400)
        self.assertEqual(self.review(comentario=None).status_code, 400)
        self.assertEqual(self.review(comentario='a' * 1000).status_code, 201)

    def test_score_boundaries_and_optional_comment(self):
        self.finish()
        self.assertEqual(self.review(nota=1).status_code, 201)
        self.assertEqual(self.review(self.worker, nota=5).status_code, 201)
        self.assertEqual(set(Avaliacao.objects.values_list('comentario', flat=True)), {''})

    def test_nonexistent_or_out_of_range_ids_do_not_leak_database_errors(self):
        for value in [2**63 - 1, 2**63, 0, -1]:
            expected = 404 if value == 2**63 - 1 else 400
            self.assertEqual(self.review(candidatura_id=value).status_code, expected)
        for value in [2**63, 10**100]:
            self.assertEqual(self.api(self.company).get(f'/api/candidaturas/{value}/conclusao/').status_code, 404)
            self.assertEqual(
                self.api(self.company).get(f'/api/avaliacoes/usuarios/{value}/reputacao/').status_code, 404
            )

    def test_jwt_is_required_on_every_endpoint(self):
        client = self.api()
        for method, path, payload in [
            ('post', '/api/avaliacoes/', {'candidatura_id': self.application.pk, 'nota': 4}),
            ('post', self.completion_url(), {}),
            ('get', self.completion_url(), {}),
            ('get', '/api/avaliacoes/minhas/', {}),
            ('get', '/api/avaliacoes/recebidas/', {}),
            ('get', f'/api/avaliacoes/usuarios/{self.worker.pk}/', {}),
            ('get', f'/api/avaliacoes/usuarios/{self.worker.pk}/reputacao/', {}),
        ]:
            response = getattr(client, method)(path, payload, format='json')
            self.assertEqual(response.status_code, 401, (path, response.data))
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid-jwt')
        self.assertEqual(client.post(self.completion_url(), {}, format='json').status_code, 401)

    def test_inactive_missing_or_ambiguous_role_is_denied(self):
        self.finish()
        for role in ['inactive', 'missing', 'ambiguous']:
            user = User.objects.create_user(f'{role}57@example.com')
            if role == 'inactive':
                user.is_active = False
                user.save(update_fields=['is_active'])
            if role == 'ambiguous':
                user.groups.add(*Group.objects.filter(name__in=['Empresa', 'Usuário']))
            expected = 401 if role == 'inactive' else 403
            self.assertEqual(self.confirm(user).status_code, expected)
            self.assertEqual(self.review(user).status_code, expected)

    def test_ownership_changes_cannot_reuse_or_replace_confirmations(self):
        self.finish()
        self.assertEqual(self.review().status_code, 201)
        before = ConclusaoTrabalho.objects.values().get()
        Freelance.objects.filter(pk=self.job.pk).update(empresa=self.other_company)
        self.assertEqual(self.confirm(self.other_company).status_code, 409)
        self.assertEqual(self.review(self.other_company).status_code, 409)
        self.assertEqual(self.reputation().data['total_avaliacoes'], 0)
        self.assertEqual(ConclusaoTrabalho.objects.values().get(), before)

    def test_user_cannot_edit_delete_or_retrieve_arbitrary_reviews(self):
        self.finish()
        result = self.review()
        for user in [self.company, self.worker, self.outsider]:
            client = self.api(user)
            for method in ['put', 'patch', 'delete']:
                self.assertIn(
                    getattr(client, method)(f'/api/avaliacoes/{result.data["id"]}/', {}, format='json').status_code,
                    {404, 405},
                )
            self.assertIn(client.get(f'/api/avaliacoes/{result.data["id"]}/').status_code, {404, 405})
        self.assertEqual(Avaliacao.objects.get().nota, 5)

    def test_received_and_sent_lists_are_separate_and_private(self):
        self.finish()
        a = self.review(nota=2)
        b = self.review(self.worker, nota=5)
        worker = self.api(self.worker)
        self.assertEqual(worker.get('/api/avaliacoes/minhas/').data['results'][0]['id'], b.data['id'])
        self.assertEqual(worker.get('/api/avaliacoes/recebidas/').data['results'][0]['id'], a.data['id'])
        self.assertEqual(self.api(self.outsider).get('/api/avaliacoes/minhas/').data['count'], 0)
        self.assertEqual(self.api(self.outsider).get('/api/avaliacoes/recebidas/').data['count'], 0)
        self.assertEqual(self.reputation().data['media'], 2)
        self.assertEqual(self.reputation(self.company).data['media'], 5)

    def test_average_counts_only_received_valid_reviews_and_excludes_removed(self):
        self.finish()
        self.assertEqual(self.review(nota=5).status_code, 201)
        self.assertEqual(self.review(self.worker, nota=1).status_code, 201)
        response = self.api(self.worker).post(
            '/api/candidaturas/', {'oportunidade': self._second_job().pk}, format='json'
        )
        second = Candidatura.objects.get(pk=response.data['id'])
        self.finish(second)
        self.assertEqual(self.review(application=second, nota=4).status_code, 201)
        self.assertEqual(self.reputation().data, {'usuario_id': self.worker.pk, 'media': 4.5, 'total_avaliacoes': 2})
        Avaliacao.objects.filter(candidatura=second).delete()
        self.assertEqual(self.reputation().data['media'], 5)
        self.assertEqual(self.reputation().data['total_avaliacoes'], 1)
        Candidatura.objects.filter(pk=self.application.pk).update(status='recusada')
        self.assertEqual(self.reputation().data['media'], None)
        self.assertEqual(self.reputation().data['total_avaliacoes'], 0)

    def test_no_reviews_gives_null_average(self):
        self.assertEqual(self.reputation().data, {'usuario_id': self.worker.pk, 'media': None, 'total_avaliacoes': 0})

    def test_public_projection_contains_no_private_identity_or_work_details(self):
        self.finish()
        self.assertEqual(self.review(comentario='Bom trabalho.').status_code, 201)
        response = self.api(self.other_company).get(f'/api/avaliacoes/usuarios/{self.worker.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data['results'][0]), {'id', 'nota', 'comentario', 'criado_em'})
        text = str(response.data)
        for private in [
            'private-phone',
            'private-google-id',
            'private-address',
            self.worker.email,
            'password',
            'candidatura',
            'avaliador',
        ]:
            self.assertNotIn(private, text)

    def test_private_profiles_hidden_and_company_reviews_do_not_disclose_b46_profile(self):
        self.finish()
        self.assertEqual(self.review(self.worker).status_code, 201)
        self.assertEqual(self.reputation(self.company).data['total_avaliacoes'], 1)
        User.objects.filter(pk=self.worker.pk).update(perfil_publico=False)
        self.assertEqual(self.reputation().status_code, 404)
        self.assertEqual(self.api(self.company).get(f'/api/avaliacoes/usuarios/{self.worker.pk}/').status_code, 404)
        self.assertEqual(self.api(self.worker).get('/api/avaliacoes/minhas/').status_code, 200)
        self.assertEqual(self.api(self.company).get('/api/avaliacoes/usuarios/999999/').status_code, 404)

    def test_invalid_rows_bypassing_api_do_not_contribute_to_reputation(self):
        # Deliberately invalid administrative writes are excluded, never used as positive fixtures.
        self.approve()
        Avaliacao.objects.create(candidatura=self.application, avaliador=self.company, avaliado=self.worker, nota=5)
        self.assertEqual(self.reputation().data['total_avaliacoes'], 0)
        Avaliacao.objects.all().delete()
        self.finish()
        Avaliacao.objects.create(candidatura=self.application, avaliador=self.outsider, avaliado=self.worker, nota=5)
        self.assertEqual(self.reputation().data['total_avaliacoes'], 0)
        self.assertEqual(self.api(self.company).get(f'/api/avaliacoes/usuarios/{self.worker.pk}/').data['count'], 0)

    def test_database_enforces_duplicate_range_and_self_constraints(self):
        self.finish()
        self.assertEqual(self.review().status_code, 201)
        for values in [
            {'avaliador': self.company, 'avaliado': self.worker, 'nota': 3},
            {'avaliador': self.worker, 'avaliado': self.company, 'nota': 0},
            {'avaliador': self.worker, 'avaliado': self.company, 'nota': 6},
            {'avaliador': self.worker, 'avaliado': self.worker, 'nota': 4},
        ]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Avaliacao.objects.create(candidatura=self.application, **values)
        self.assertEqual(Avaliacao.objects.count(), 1)

    def test_cascades_remove_reviews_and_reputation(self):
        self.finish()
        self.assertEqual(self.review().status_code, 201)
        self.job.delete()
        self.assertFalse(ConclusaoTrabalho.objects.exists())
        self.assertFalse(Avaliacao.objects.exists())
        self.assertEqual(self.reputation().data['total_avaliacoes'], 0)

    def test_database_contention_is_controlled_and_does_not_partially_write(self):
        self.approve()
        with patch(
            'core.avaliacoes.ConclusaoTrabalho.objects.get_or_create', side_effect=OperationalError('private SQL')
        ):
            result = self.confirm(self.company)
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('private SQL', str(result.data))
        self.assertFalse(ConclusaoTrabalho.objects.exists())
        self.finish()
        with patch('core.avaliacoes.Avaliacao.objects.create', side_effect=OperationalError('private SQL')):
            result = self.review()
        self.assertEqual(result.status_code, 503)
        self.assertFalse(Avaliacao.objects.exists())

    def test_queries_are_bounded_and_public_lists_use_real_pagination(self):
        self.finish()
        self.assertEqual(self.review().status_code, 201)
        client = self.api(self.company)
        path = f'/api/avaliacoes/usuarios/{self.worker.pk}/'
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(client.get(path).data['count'], 1)
        for _ in range(10):
            result = self.api(self.worker).post(
                '/api/candidaturas/', {'oportunidade': self._second_job().pk}, format='json'
            )
            application = Candidatura.objects.get(pk=result.data['id'])
            self.finish(application)
            self.assertEqual(self.review(application=application).status_code, 201)
        with CaptureQueriesContext(connection) as many:
            response = client.get(path)
        self.assertEqual(len(first), len(many))
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        next_page = client.get(response.data['next'])
        self.assertEqual(len(next_page.data['results']), 1)
        ids = [r['id'] for r in response.data['results'] + next_page.data['results']]
        self.assertEqual(len(set(ids)), 11)
        with CaptureQueriesContext(connection) as aggregate:
            self.assertEqual(client.get(f'{path}reputacao/').data['total_avaliacoes'], 11)
        self.assertEqual(sum('AVG(' in q['sql'].upper() and 'COUNT(' in q['sql'].upper() for q in aggregate), 1)

    def test_openapi_documents_completion_payload_and_every_review_route(self):
        from drf_spectacular.generators import SchemaGenerator  # noqa: PLC0415

        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema['paths']
        for path in [
            '/api/avaliacoes/',
            '/api/avaliacoes/minhas/',
            '/api/avaliacoes/recebidas/',
            '/api/avaliacoes/usuarios/{usuario_id}/',
            '/api/avaliacoes/usuarios/{usuario_id}/reputacao/',
            '/api/candidaturas/{candidatura_id}/conclusao/',
        ]:
            self.assertIn(path, paths)
        self.assertEqual(set(paths['/api/avaliacoes/']), {'post'})
        self.assertIn('201', paths['/api/avaliacoes/']['post']['responses'])
        self.assertIn('409', paths['/api/avaliacoes/']['post']['responses'])


class AvaliacaoConcurrencyTests(TrabalhoFixture, TransactionTestCase):
    def run_concurrently(self, operations):
        barrier = Barrier(len(operations))

        def execute(operation):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(execute, operation) for operation in operations]
            return [future.result(timeout=30) for future in futures]

    def test_simultaneous_duplicate_reviews_never_create_duplicate_records(self):
        self.finish()
        token = str(RefreshToken.for_user(self.company).access_token)

        def send():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            return client.post('/api/avaliacoes/', {'candidatura_id': self.application.pk, 'nota': 5}, format='json')

        results = self.run_concurrently([send, send])
        for result in results:
            self.assertIn(result.status_code, {201, 409, 503}, result.data)
        retry = send()
        self.assertIn(retry.status_code, {201, 409}, retry.data)
        self.assertEqual(Avaliacao.objects.count(), 1)
        self.assertEqual(Avaliacao.objects.validas().count(), 1)

    def test_simultaneous_confirmations_and_retries_preserve_both_evidences(self):
        self.approve()
        results = self.run_concurrently([
            lambda: self.confirm(self.company),
            lambda: self.confirm(self.worker),
        ])
        for result in results:
            self.assertIn(result.status_code, {200, 503}, result.data)
        for user in [self.company, self.worker]:
            self.assertEqual(self.confirm(user).status_code, 200)
        self.assertEqual(ConclusaoTrabalho.objects.count(), 1)
        self.assertTrue(ConclusaoTrabalho.objects.get().concluido)
        self.assertEqual(self.review().status_code, 201)


class AvaliacaoMigrationTests(TransactionTestCase):
    def test_legacy_approved_applications_do_not_get_completion_or_ratings(self):
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('core', '0022_empresa_perfil')])
            apps = executor.loader.project_state([('core', '0022_empresa_perfil')]).apps
            users = apps.get_model('core', 'User')
            jobs = apps.get_model('core', 'Freelance')
            applications = apps.get_model('core', 'Candidatura')
            company = users.objects.create(email='legacy-company57@example.com', password='!')
            worker = users.objects.create(email='legacy-worker57@example.com', password='!')
            job = jobs.objects.create(
                empresa_id=company.pk, titulo='Legada', preco=1, tempo='1 dia', status='encerrada'
            )
            application = applications.objects.create(
                freelancer_id=worker.pk, oportunidade_id=job.pk, status='aprovada'
            )
            before = list(applications.objects.values())
            executor = MigrationExecutor(connection)
            executor.migrate(latest_targets)
            self.assertEqual(list(Candidatura.objects.values()), before)
            self.assertEqual(Candidatura.objects.get(pk=application.pk).status, 'aprovada')
            self.assertFalse(ConclusaoTrabalho.objects.exists())
            self.assertFalse(Avaliacao.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(latest_targets)
