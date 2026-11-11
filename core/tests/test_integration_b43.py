"""B43 API journeys through the real router, registration and JWT middleware.

Level B: Django's in-process HTTP client, disposable database, no deployed server.
Module-level edge cases remain covered by the existing 270 tests.
"""

# ruff: noqa: PT009, PT027
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import Candidatura, EmpresaPerfil, Favorito, Freelance, Notificacao, Portfolio, User


class BackendJourneyTests(APITestCase):
    password = 'Synthetic-B43-73829!'

    def setUp(self):
        self.actors = {}
        self.ids = {}
        for name, role in [
            ('company_a', 'empresa'),
            ('company_b', 'empresa'),
            ('worker_a', 'usuario'),
            ('worker_b', 'usuario'),
        ]:
            self.register_actor(name, role)

    def register_actor(self, name, role):
        client = APIClient()
        email = f'{name}@b43.example.invalid'
        response = client.post(
            '/api/registro/',
            {
                'email': email,
                'password': self.password,
                'tipo': role,
                'name': name,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password', response.data)
        self.ids[name] = response.data['id']
        response = client.post('/api/token/', {'email': email, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        profile = client.get('/api/usuarios/me/')
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data['tipo'], role)
        self.actors[name] = client

    def call(self, actor, method, path, data=None, expected=200):
        client = self.actors[actor] if actor else APIClient()
        response = getattr(client, method)(path, data, format='json')
        self.assertEqual(response.status_code, expected, f'{actor} {method} {path}')
        return response.data

    def create_job(self):
        job = self.call(
            'company_a',
            'post',
            '/api/freelances/',
            {
                'titulo': 'Python & API B43',
                'descricao': 'Synthetic integration opportunity',
                'preco': '500.00',
                'tempo': '10 dias',
                'tag': 'Python',
                'modalidade': 'Remoto',
                'cidade': 'Joinville',
                'uf': 'SC',
                'status': 'publicada',
                'tipo_contratacao': 'PJ',
                'nivel_experiencia': 'Pleno',
                'empresa': self.ids['company_b'],
            },
            expected=201,
        )
        self.assertEqual(job['empresa'], self.ids['company_a'])
        return job['id']

    def publish_worker(self):
        self.call(
            'worker_a',
            'patch',
            '/api/usuarios/me/',
            {
                'name': 'Professional & B43',
                'profissao': 'Backend',
                'habilidades': ['Python'],
                'sobre': 'Synthetic professional profile',
                'telefone': '(47) 99999-9999',
                'localizacao': 'Private synthetic location',
                'latitude': -26,
                'longitude': -48,
                'perfil_publico': True,
                'cidade_publica': 'Joinville',
            },
        )
        public = self.call(
            'worker_a',
            'post',
            '/api/portfolios/',
            {
                'titulo': 'Published B43',
                'categoria': 'Backend',
                'descricao': 'Synthetic project',
                'tags': ['Python'],
                'publico': True,
                'usuario': self.ids['worker_b'],
            },
            expected=201,
        )
        self.call(
            'worker_a',
            'post',
            '/api/portfolios/',
            {
                'titulo': 'Private B43',
                'categoria': 'Backend',
                'descricao': 'Private synthetic project',
                'publico': False,
            },
            expected=201,
        )
        self.assertEqual(Portfolio.objects.get(pk=public['id']).usuario_id, self.ids['worker_a'])
        return public['id']

    def test_registered_accounts_complete_publication_application_and_decision_journey(self):  # noqa: PLR0914, PLR0915
        # Every business operation uses HTTP and tokens obtained through /api/token/.
        company = self.call('company_a', 'get', '/api/empresas/me/')
        self.assertEqual(company['empresa'], self.ids['company_a'])
        self.assertFalse(EmpresaPerfil.objects.exists())
        self.call(
            'company_a',
            'patch',
            '/api/empresas/me/',
            {
                'name': 'Company & B43',
                'descricao_institucional': 'Synthetic company',
                'contato_comercial': 'Internal synthetic contact',
                'empresa': self.ids['company_b'],
            },
        )
        self.assertEqual(EmpresaPerfil.objects.get().empresa_id, self.ids['company_a'])
        project_id = self.publish_worker()
        directory = self.call(
            'company_a',
            'get',
            '/api/freelancers/',
            {
                'cidade': 'joinville',
                'habilidade': 'python',
            },
        )
        self.assertEqual([row['id'] for row in directory['results']], [self.ids['worker_a']])
        public_profile = self.call('company_a', 'get', f'/api/freelancers/{self.ids["worker_a"]}/')
        self.assertEqual([row['id'] for row in public_profile['portfolio']], [project_id])
        for field in ['email', 'telefone', 'latitude', 'longitude', 'geolocation_accuracy', 'geolocation_timestamp']:
            self.assertNotIn(field, public_profile)
        job_id = self.create_job()
        jobs = self.call(
            'worker_a',
            'get',
            '/api/freelances/',
            {
                'search': 'Python',
                'tag': 'python',
                'preco_min': '499',
                'preco_max': '501',
                'tipo_contratacao': 'PJ',
                'nivel_experiencia': 'Pleno',
            },
        )
        self.assertEqual([row['id'] for row in jobs['results']], [job_id])
        favorite = self.call('worker_a', 'post', '/api/favoritos/', {'oportunidade': job_id}, expected=201)
        repeated = self.call('worker_a', 'post', '/api/favoritos/', {'oportunidade': job_id})
        self.assertEqual(favorite['id'], repeated['id'])
        self.assertEqual(self.call('worker_a', 'get', '/api/favoritos/')['count'], 1)
        self.assertEqual(self.call('worker_b', 'get', '/api/favoritos/')['count'], 0)
        application = self.call(
            'worker_a',
            'post',
            '/api/candidaturas/',
            {
                'oportunidade': job_id,
                'freelancer': self.ids['worker_b'],
                'status': 'aprovada',
            },
            expected=201,
        )
        application_id = application['id']
        self.assertEqual(application['freelancer'], self.ids['worker_a'])
        self.assertEqual(application['status'], 'pendente')
        notifications = self.call('company_a', 'get', '/api/notificacoes/', {'lida': 'false'})
        self.assertEqual(notifications['count'], 1)
        notification_id = notifications['results'][0]['id']
        self.assertEqual(notifications['results'][0]['candidatura'], application_id)
        self.assertEqual(self.call('company_b', 'get', '/api/notificacoes/')['count'], 0)
        self.call('worker_a', 'post', '/api/candidaturas/', {'oportunidade': job_id}, expected=400)
        self.assertEqual(Candidatura.objects.count(), 1)
        self.assertEqual(Notificacao.objects.count(), 1)
        pending = self.call('company_a', 'get', f'/api/candidaturas/{application_id}/')
        self.assertFalse(pending['whatsapp']['disponivel'])
        self.call(
            'company_a',
            'patch',
            f'/api/notificacoes/{notification_id}/marcar-lida/',
            {
                'empresa': self.ids['company_b'],
                'lida': False,
            },
        )
        notification = Notificacao.objects.get(pk=notification_id)
        self.assertTrue(notification.lida)
        self.assertEqual(notification.empresa_id, self.ids['company_a'])
        before = Candidatura.objects.get(pk=application_id).atualizado_em
        approved = self.call('company_a', 'post', f'/api/candidaturas/{application_id}/aprovar/')
        self.assertEqual(approved['status'], 'aprovada')
        self.assertGreaterEqual(Candidatura.objects.get(pk=application_id).atualizado_em, before)
        contact = approved['whatsapp']
        self.assertTrue(contact['disponivel'])
        self.assertFalse(contact['mensagem_enviada'])
        parsed = urlparse(contact['url'])
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ('https', 'wa.me', '/5547999999999'))
        self.assertIn('Python & API B43', parse_qs(parsed.query)['text'][0])
        self.assertIn('%26', parsed.query)
        self.call('company_a', 'post', f'/api/candidaturas/{application_id}/aprovar/')
        self.call('company_a', 'post', f'/api/candidaturas/{application_id}/recusar/', expected=409)
        self.assertEqual(Candidatura.objects.get(pk=application_id).status, 'aprovada')
        self.assertEqual(self.call('worker_a', 'get', f'/api/candidaturas/{application_id}/')['status'], 'aprovada')
        self.assertEqual(self.call('company_a', 'get', '/api/notificacoes/', {'status': 'aprovada'})['count'], 1)
        self.call('worker_a', 'patch', '/api/usuarios/me/', {'perfil_publico': False})
        self.call('company_a', 'get', f'/api/freelancers/{self.ids["worker_a"]}/', expected=404)
        self.assertEqual(self.call('worker_a', 'get', f'/api/portfolios/{project_id}/')['id'], project_id)
        self.call('worker_a', 'delete', f'/api/favoritos/{favorite["id"]}/', expected=204)
        self.call('company_a', 'patch', f'/api/freelances/{job_id}/', {'status': 'encerrada'})
        self.assertEqual(Freelance.objects.get(pk=job_id).status, 'encerrada')
        self.call('company_a', 'delete', f'/api/freelances/{job_id}/', expected=204)
        self.assertFalse(Candidatura.objects.exists())
        self.assertFalse(Notificacao.objects.exists())
        self.assertFalse(Favorito.objects.exists())

    def business_snapshot(self):
        # No passwords, tokens or email values in snapshot assertion diagnostics.
        return {
            model.__name__: list(model.objects.order_by('pk').values())
            for model in [Freelance, Portfolio, Candidatura, Notificacao, EmpresaPerfil, Favorito]
        }

    def test_http_role_matrix_denied_operations_leave_business_database_unchanged(self):
        job_id = self.create_job()
        project_id = self.publish_worker()
        application = self.call('worker_a', 'post', '/api/candidaturas/', {'oportunidade': job_id}, expected=201)
        application_id = application['id']
        notification_id = Notificacao.objects.get().pk
        self.register_actor('inactive', 'usuario')
        User.objects.filter(pk=self.ids['inactive']).update(is_active=False)
        self.register_actor('ambiguous', 'empresa')
        User.objects.get(pk=self.ids['ambiguous']).groups.add(Group.objects.get(name='Usuário'))
        # Column order is the actor order below. Expected codes follow real querysets.
        actors = ['company_a', 'company_b', 'worker_a', 'worker_b', None, 'inactive', 'ambiguous']
        rows = [
            ('patch', f'/api/freelances/{job_id}/', {'titulo': 'Allowed B43'}, [200, 403, 403, 403, 401, 401, 403]),
            ('patch', f'/api/portfolios/{project_id}/', {'titulo': 'Allowed B43'}, [403, 403, 200, 404, 401, 401, 403]),
            ('get', f'/api/candidaturas/{application_id}/', None, [200, 404, 200, 404, 401, 401, 403]),
            ('post', f'/api/candidaturas/{application_id}/aprovar/', None, [200, 404, 403, 403, 401, 401, 403]),
            ('patch', f'/api/notificacoes/{notification_id}/marcar-lida/', {}, [200, 404, 403, 403, 401, 401, 403]),
            ('get', f'/api/freelancers/{self.ids["worker_a"]}/', None, [200, 200, 403, 403, 401, 401, 403]),
        ]
        for method, path, data, codes in rows:
            for actor, code in zip(actors, codes, strict=True):
                with self.subTest(actor=actor, method=method, path=path):
                    before = self.business_snapshot()
                    self.call(actor, method, path, data, expected=code)
                    if code >= status.HTTP_400_BAD_REQUEST:
                        self.assertEqual(before, self.business_snapshot())

    def test_documentation_routes_return_responses_and_schema_has_real_resources(self):
        # Schema diagnostics are kept visible; serving docs does not validate completeness.
        for path in ['/api/doc/', '/api/redoc/']:
            response = APIClient().get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/html', response['Content-Type'])
        response = APIClient().get('/api/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        paths = response.data['paths']
        for path in [
            '/api/freelances/',
            '/api/freelancers/',
            '/api/candidaturas/',
            '/api/notificacoes/',
            '/api/empresas/me/',
        ]:
            self.assertIn(path, paths)
