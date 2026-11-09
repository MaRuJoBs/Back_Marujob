# ruff: noqa: PT009, PT027
from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import include, path, resolve
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app.urls import router
from core.models import Portfolio, User
from core.serializers.freelancer_publico import (
    FreelancerPublicoDetailSerializer,
    FreelancerPublicoListSerializer,
)


class FreelancerPublicoTests(APITestCase):
    url = '/api/freelancers/'

    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('company-b45@example.com', 'test-password')
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.worker = User.objects.create_user(
            'worker-b45@example.com', 'test-password', name='Ana Silva',
            profissao='Designer', habilidades=['Python', 'Figma'],
            localizacao='Endereço residencial confidencial', sobre='Privado',
            telefone='999999999', latitude=12, longitude=34,
            perfil_configurado=True,
        )
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.portfolio = Portfolio.objects.create(
            usuario=cls.worker, titulo='Projeto privado', categoria='Design',
            descricao='Informação confidencial',
        )

    def authenticate(self, user=None, expired=False):
        token = RefreshToken.for_user(user or self.company).access_token
        if expired:
            token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_company_list_is_paginated_and_empty_without_consent(self):
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'count': 0, 'next': None, 'previous': None, 'results': []})

    def test_missing_invalid_and_expired_jwt_on_both_routes(self):
        for url in (self.url, f'{self.url}{self.worker.pk}/'):
            self.client.credentials()
            self.assertEqual(self.client.get(url).status_code, 401)
            self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
            self.assertEqual(self.client.get(url).status_code, 401)
            self.authenticate(expired=True)
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_freelancer_and_untyped_users_are_forbidden(self):
        untyped = User.objects.create_user('untyped-b45@example.com')
        for user in (self.worker, untyped):
            self.authenticate(user)
            for url in (self.url, f'{self.url}{self.worker.pk}/'):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_dual_group_company_is_forbidden(self):
        self.company.groups.add(Group.objects.get(name='Usuário'))
        self.authenticate()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 403)

    def test_inactive_company_token_is_rejected(self):
        self.authenticate()
        self.company.is_active = False
        self.company.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 401)

    def test_all_existing_and_missing_profiles_are_hidden(self):
        self.authenticate()
        for pk in (self.worker.pk, self.company.pk, 999999):
            response = self.client.get(f'{self.url}{pk}/')
            self.assertEqual(response.status_code, 404)
            self.assertEqual(set(response.data), {'detail'})

    def test_inactive_administrative_dual_and_optional_profiles_are_hidden(self):
        self.authenticate()
        variants = [
            {'is_active': False}, {'is_staff': True}, {'is_superuser': True},
            {'name': None, 'profissao': '', 'habilidades': [], 'perfil_configurado': False},
        ]
        for index, attrs in enumerate(variants):
            user = User.objects.create_user(f'hidden-b45-{index}@example.com', **attrs)
            user.groups.add(Group.objects.get(name='Usuário'))
            self.assertEqual(self.client.get(f'{self.url}{user.pk}/').status_code, 404)
        self.worker.groups.add(Group.objects.get(name='Empresa'))
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 404)
        self.assertEqual(self.client.get(self.url).data['count'], 0)

    def test_nonempty_filters_explicitly_unavailable(self):
        self.authenticate()
        for key, value in (
            ('search', ' ana  SILVA '), ('profissao', 'DESIGNER'),
            ('habilidade', 'Python'), ('cidade', 'Joinville'),
        ):
            response = self.client.get(self.url, {key: value})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(set(response.data), {key})

    def test_combined_filters_are_not_silently_ignored(self):
        self.authenticate()
        response = self.client.get(self.url, {'search': 'Ana', 'cidade': 'Joinville', 'habilidade': 'Python'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {'search', 'cidade', 'habilidade'})

    def test_empty_and_whitespace_filters_are_accepted(self):
        self.authenticate()
        response = self.client.get(self.url, {'search': '   ', 'profissao': '', 'habilidade': '\t', 'cidade': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])

    def test_unknown_repeated_and_oversized_parameters(self):
        self.authenticate()
        for query in (
            '?search=a&search=b', '?page=1&page=2', '?ordering=email',
            '?page_size=999999', '?habilidade=' + 'a' * 101, '?search=' + 'a' * 256,
        ):
            self.assertEqual(self.client.get(self.url + query).status_code, 400)

    def test_page_validation_and_empty_second_page(self):
        self.authenticate()
        self.assertEqual(self.client.get(self.url, {'page': 1}).status_code, 200)
        self.assertEqual(self.client.get(self.url, {'page': 2}).status_code, 404)
        for page in ('0', '-1', 'abc', '1.5', '', '1000001'):
            self.assertEqual(self.client.get(self.url, {'page': page}).status_code, 400)

    def test_read_only_endpoints(self):
        self.authenticate()
        for url in (self.url, f'{self.url}{self.worker.pk}/'):
            for method in ('post', 'put', 'patch', 'delete'):
                self.assertEqual(getattr(self.client, method)(url, {}, format='json').status_code, 405)

    def test_private_values_never_appear_in_api_json(self):
        self.authenticate()
        for url in (self.url, f'{self.url}{self.worker.pk}/'):
            response = self.client.get(url)
            payload = response.content.decode()
            for value in (
                self.worker.email, self.worker.telefone, self.worker.localizacao,
                self.portfolio.titulo, self.portfolio.descricao, 'password', 'latitude',
                'longitude', 'last_login', 'groups', 'is_staff', 'is_superuser',
                'user_permissions', 'google_id', 'refresh', 'access', 'geolocation',
            ):
                self.assertNotIn(value, payload)

    def test_no_profile_or_portfolio_queries_on_list(self):
        self.authenticate()
        # JWT loads requester and account_type loads groups; no directory data is read.
        with self.assertNumQueries(2):
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_existing_routes_are_preserved(self):
        for route, basename in (
            ('freelances', 'freelances'), ('portfolios', 'portfolios'), ('usuarios', 'usuarios'),
        ):
            self.assertEqual(resolve(f'/api/{route}/').url_name, f'{basename}-list')


class FreelancerPublicoContractTests(TestCase):
    def test_explicit_allowlists_and_portfolio_non_disclosure(self):
        # Serializer contract only: this does not simulate authorized publication.
        user = User(id=42, email='private@example.com', name='Private', habilidades=['Private'])
        self.assertEqual(FreelancerPublicoListSerializer(user).data, {'id': 42})
        self.assertEqual(FreelancerPublicoDetailSerializer(user).data, {'id': 42, 'portfolio': []})

    def test_openapi_exposes_routes_and_partial_delivery(self):
        schema = SchemaGenerator(patterns=[path('api/', include(router.urls))]).get_schema(public=True)
        operation = schema['paths']['/api/freelancers/']['get']
        self.assertIn('entrega parcial', operation['summary'])
        self.assertTrue({'200', '400', '401', '403'} <= set(operation['responses']))
        self.assertIn('/api/freelancers/{id}/', schema['paths'])
        self.assertTrue(
            {'search', 'profissao', 'habilidade', 'cidade', 'page'}
            <= {parameter['name'] for parameter in operation['parameters']}
        )
