# ruff: noqa: PT009, PT027, PLR0904
from datetime import timedelta

from django.contrib.auth.models import Group
from django.db import connection
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db.migrations.executor import MigrationExecutor
from django.db.models import F, Value
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import include, path, resolve
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app.urls import router
from core.freelancer_filters import HabilidadeIExact
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
            'worker-b45@example.com',
            'test-password',
            name='Ana Silva',
            profissao='Designer',
            habilidades=['Python', 'Figma'],
            localizacao='Endereço residencial confidencial',
            sobre='Privado',
            telefone='999999999',
            latitude=12,
            longitude=34,
            perfil_configurado=True,
            perfil_publico=True,
            cidade_publica='Joinville',
        )
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.portfolio = Portfolio.objects.create(
            usuario=cls.worker,
            titulo='Projeto privado',
            categoria='Design',
            descricao='Informação confidencial',
        )

    def authenticate(self, user=None, expired=False):
        token = RefreshToken.for_user(user or self.company).access_token
        if expired:
            token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_company_list_is_paginated_and_published(self):
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertIsNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        self.assertEqual(response.data['results'][0]['nome'], 'Ana Silva')
        self.assertEqual(response.data['results'][0]['cidade'], 'Joinville')

    def test_private_profile_is_excluded_even_when_configured(self):
        self.worker.perfil_publico = False
        self.worker.save()
        self.authenticate()
        self.assertEqual(self.client.get(self.url).data['results'], [])
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 404)

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

    def test_public_detail_and_ineligible_or_missing_profiles(self):
        self.authenticate()
        detail = self.client.get(f'{self.url}{self.worker.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['descricao'], self.worker.sobre)
        self.assertEqual(detail.data['portfolio'], [])
        for pk in (self.company.pk, 999999):
            response = self.client.get(f'{self.url}{pk}/')
            self.assertEqual(response.status_code, 404)
            self.assertEqual(set(response.data), {'detail'})

    def test_inactive_administrative_and_dual_profiles_are_hidden(self):
        self.authenticate()
        variants = [
            {'is_active': False},
            {'is_staff': True},
            {'is_superuser': True},
        ]
        for index, attrs in enumerate(variants):
            user = User.objects.create_user(f'hidden-b45-{index}@example.com', perfil_publico=True, **attrs)
            user.groups.add(Group.objects.get(name='Usuário'))
            self.assertEqual(self.client.get(f'{self.url}{user.pk}/').status_code, 404)
        self.worker.groups.add(Group.objects.get(name='Empresa'))
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 404)
        self.assertEqual(self.client.get(self.url).data['count'], 0)

    def test_filters_case_insensitive_and_normalized(self):
        self.authenticate()
        for key, value in (
            ('search', ' ana  SILVA '),
            ('profissao', 'DESIGNER'),
            ('habilidade', 'Python'),
            ('cidade', 'Joinville'),
        ):
            response = self.client.get(self.url, {key: value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([item['id'] for item in response.data['results']], [self.worker.pk])

    def test_combined_filters_are_not_silently_ignored(self):
        self.authenticate()
        response = self.client.get(self.url, {'search': 'Ana', 'cidade': 'Joinville', 'habilidade': 'Python'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        response = self.client.get(self.url, {'cidade': 'Blumenau', 'habilidade': 'Python'})
        self.assertEqual(response.data['count'], 0)

    def test_empty_and_whitespace_filters_are_accepted(self):
        self.authenticate()
        response = self.client.get(self.url, {'search': '   ', 'profissao': '', 'habilidade': '\t', 'cidade': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_unknown_repeated_and_oversized_parameters(self):
        self.authenticate()
        for query in (
            '?search=a&search=b',
            '?page=1&page=2',
            '?ordering=email',
            '?page_size=999999',
            '?habilidade=' + 'a' * 101,
            '?search=' + 'a' * 256,
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
                self.worker.email,
                self.worker.telefone,
                self.worker.localizacao,
                self.portfolio.titulo,
                self.portfolio.descricao,
                'password',
                'latitude',
                'longitude',
                'last_login',
                'groups',
                'is_staff',
                'is_superuser',
                'user_permissions',
                'google_id',
                'refresh',
                'access',
                'geolocation',
            ):
                self.assertNotIn(value, payload)

    def test_list_query_count_is_constant(self):
        self.authenticate()
        # JWT, groups, count and paginated users; no portfolio query on list.
        with self.assertNumQueries(4):
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_existing_routes_are_preserved(self):
        for route, basename in (
            ('freelances', 'freelances'),
            ('portfolios', 'portfolios'),
            ('usuarios', 'usuarios'),
        ):
            self.assertEqual(resolve(f'/api/{route}/').url_name, f'{basename}-list')

    def test_optional_fields_do_not_require_private_profile_completion(self):
        User.objects.filter(pk=self.worker.pk).update(
            name=None,
            profissao='',
            cidade_publica='',
            sobre='',
            habilidades=[],
            perfil_configurado=False,
        )
        self.authenticate()
        response = self.client.get(f'{self.url}{self.worker.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['nome'])
        self.assertIsNone(response.data['foto_perfil'])
        self.assertEqual(response.data['habilidades'], [])

    def test_untyped_and_company_accounts_excluded_even_with_public_flag(self):
        self.company.perfil_publico = True
        self.company.save()
        User.objects.create_user('no-role@example.com', perfil_publico=True)
        self.authenticate()
        self.assertEqual(self.client.get(self.url).data['count'], 1)

    def test_search_does_not_search_private_data_or_unpublished_profiles(self):
        self.authenticate()
        for field, value in (
            ('search', self.worker.email),
            ('search', self.worker.telefone),
            ('cidade', self.worker.localizacao),
            ('search', 'Nome inexistente'),
        ):
            response = self.client.get(self.url, {field: value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 0)
        User.objects.filter(pk=self.worker.pk).update(perfil_publico=False)
        self.assertEqual(self.client.get(self.url, {'search': 'Ana'}).data['count'], 0)

    def test_skill_matches_whole_string_and_not_json_substrings(self):
        self.authenticate()
        for skills in (['Pythonista'], ['CPython'], {'name': 'Python'}, 'Python', [True, 12], [['Python']]):
            User.objects.filter(pk=self.worker.pk).update(habilidades=skills)
            self.assertEqual(self.client.get(self.url, {'habilidade': 'python'}).data['count'], 0)
        for skill in ('Python', 'C++', 'Vue.js', 'GESTÃO', "x' OR 1=1 --", '100%_'):
            User.objects.filter(pk=self.worker.pk).update(habilidades=[skill, skill])
            response = self.client.get(self.url, {'habilidade': skill.lower()})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.client.get(self.url, {'habilidade': '100'}).data['count'], 0)

    def test_unicode_and_regex_characters_are_literal_in_text_filters(self):
        User.objects.filter(pk=self.worker.pk).update(
            name='João [Dev]',
            profissao='Gestão (Web)',
            cidade_publica='São José',
        )
        self.authenticate()
        for key, value in (
            ('search', 'JOÃO [dev]'),
            ('profissao', 'GESTÃO (web)'),
            ('cidade', 'SÃO JOSÉ'),
        ):
            self.assertEqual(self.client.get(self.url, {key: value}).data['count'], 1)
        self.assertEqual(self.client.get(self.url, {'search': '.*'}).data['count'], 0)

    def test_pagination_order_links_counts_and_filter_before_pagination(self):
        for index in range(12):
            user = User.objects.create_user(
                f'page-b45-{index}@example.com',
                name=f'Pessoa {index}',
                perfil_publico=True,
                cidade_publica='Blumenau',
            )
            user.groups.add(Group.objects.get(name='Usuário'))
            user.groups.add(Group.objects.create(name=f'Extra {index}'))
        self.authenticate()
        first = self.client.get(self.url).data
        second = self.client.get(self.url, {'page': 2}).data
        self.assertEqual(first['count'], 13)
        self.assertEqual(len(first['results']), 10)
        self.assertEqual(len(second['results']), 3)
        self.assertIsNone(first['previous'])
        self.assertIsNotNone(first['next'])
        self.assertIsNotNone(second['previous'])
        self.assertIsNone(second['next'])
        ids = [item['id'] for item in first['results'] + second['results']]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(self.client.get(self.url).data, first)
        filtered = self.client.get(self.url, {'cidade': 'joinville'}).data
        self.assertEqual(filtered['count'], 1)
        self.assertIsNone(filtered['next'])

    def test_owner_can_publish_and_revoke_profile_using_me(self):
        User.objects.filter(pk=self.worker.pk).update(perfil_publico=False, cidade_publica='')
        self.authenticate(self.worker)
        response = self.client.patch(
            '/api/usuarios/me/',
            {
                'perfil_publico': True,
                'cidade_publica': '  Joinville   SC ',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cidade_publica'], 'Joinville SC')
        self.assertTrue(response.data['perfil_publico'])
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.localizacao, 'Endereço residencial confidencial')
        self.authenticate()
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 200)
        self.authenticate(self.worker)
        self.assertEqual(
            self.client.patch('/api/usuarios/me/', {'perfil_publico': False}, format='json').status_code, 200
        )
        self.authenticate()
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 404)

    def test_only_freelancer_can_edit_publication_fields(self):
        for user in (self.company, User.objects.create_user('no-publish@example.com')):
            self.authenticate(user)
            response = self.client.patch('/api/usuarios/me/', {'perfil_publico': True}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                self.client.patch('/api/usuarios/me/', {'cidade_publica': 'Joinville'}, format='json').status_code, 400
            )
            # Existing company profile editing remains available.
            self.assertEqual(self.client.patch('/api/usuarios/me/', {'name': 'Nome'}, format='json').status_code, 200)
        self.worker.groups.add(Group.objects.get(name='Empresa'))
        self.authenticate(self.worker)
        self.assertEqual(
            self.client.patch('/api/usuarios/me/', {'perfil_publico': True}, format='json').status_code, 400
        )

    def test_other_account_cannot_publish_profile_and_defaults_are_private(self):
        other = User.objects.create_user('private-default@example.com', localizacao='Endereço')
        other.groups.add(Group.objects.get(name='Usuário'))
        self.assertFalse(other.perfil_publico)
        self.assertEqual(other.cidade_publica, '')
        self.authenticate()
        self.assertEqual(
            self.client.patch(f'/api/usuarios/{other.pk}/', {'perfil_publico': True}, format='json').status_code, 405
        )
        other.refresh_from_db()
        self.assertFalse(other.perfil_publico)

    def test_publication_field_validation(self):
        self.authenticate(self.worker)
        for payload in (
            {'perfil_publico': 'invalid'},
            {'perfil_publico': None},
            {'cidade_publica': 'x' * 121},
            {'cidade_publica': None},
        ):
            self.assertEqual(self.client.patch('/api/usuarios/me/', payload, format='json').status_code, 400)

    def test_multipart_publication_flags(self):
        self.authenticate(self.worker)
        response = self.client.patch('/api/usuarios/me/', {'perfil_publico': 'false'}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['perfil_publico'])
        response = self.client.patch(f'/api/portfolios/{self.portfolio.pk}/', {'publico': 'true'}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['publico'])

    def test_project_publication_and_revocation_are_owner_only(self):
        self.assertFalse(self.portfolio.publico)
        self.authenticate(self.worker)
        url = f'/api/portfolios/{self.portfolio.pk}/'
        self.assertEqual(self.client.patch(url, {'publico': True}, format='json').status_code, 200)
        self.authenticate()
        detail = self.client.get(f'{self.url}{self.worker.pk}/').data
        self.assertEqual([project['id'] for project in detail['portfolio']], [self.portfolio.pk])
        self.assertEqual(
            set(detail['portfolio'][0]), {'id', 'titulo', 'categoria', 'descricao', 'tags', 'link', 'imagem'}
        )
        self.assertEqual(self.client.patch(url, {'publico': False}, format='json').status_code, 403)
        other = User.objects.create_user('other-project@example.com')
        other.groups.add(Group.objects.get(name='Usuário'))
        self.authenticate(other)
        self.assertEqual(self.client.patch(url, {'publico': False}, format='json').status_code, 404)
        self.authenticate(self.worker)
        self.assertEqual(self.client.patch(url, {'publico': False}, format='json').status_code, 200)
        self.authenticate()
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').data['portfolio'], [])

    def test_private_profile_hides_even_published_projects(self):
        Portfolio.objects.filter(pk=self.portfolio.pk).update(publico=True)
        User.objects.filter(pk=self.worker.pk).update(perfil_publico=False)
        self.authenticate()
        self.assertEqual(self.client.get(f'{self.url}{self.worker.pk}/').status_code, 404)

    def test_public_and_private_projects_are_separated_and_ordered(self):
        public = [
            Portfolio.objects.create(
                usuario=self.worker,
                titulo=f'Publicado {index}',
                categoria='Design',
                descricao='Texto',
                publico=True,
            )
            for index in range(3)
        ]
        self.authenticate()
        with self.assertNumQueries(4):
            response = self.client.get(f'{self.url}{self.worker.pk}/')
        self.assertEqual([project['id'] for project in response.data['portfolio']], [project.pk for project in public])
        self.assertNotIn(self.portfolio.titulo, response.content.decode())

    def test_portfolio_create_can_publish_and_crud_remains_available(self):
        self.authenticate(self.worker)
        response = self.client.post(
            '/api/portfolios/',
            {
                'titulo': 'Novo',
                'categoria': 'Design',
                'descricao': 'Descrição',
                'publico': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        url = f'/api/portfolios/{response.data["id"]}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'titulo': 'Editado'}, format='json').status_code, 200)
        self.assertTrue(self.client.get(url).data['publico'])
        self.assertEqual(self.client.delete(url).status_code, 204)

    @override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}})
    def test_image_urls_are_serialized_with_request_context(self):
        User.objects.filter(pk=self.worker.pk).update(profile_image='users/public.jpg')
        Portfolio.objects.filter(pk=self.portfolio.pk).update(publico=True, imagem='portfolios/public.jpg')
        self.authenticate()
        response = self.client.get(f'{self.url}{self.worker.pk}/')
        self.assertTrue(response.data['foto_perfil'].endswith('/media/users/public.jpg'))
        self.assertTrue(response.data['portfolio'][0]['imagem'].endswith('/media/portfolios/public.jpg'))


class FreelancerPublicoContractTests(TestCase):
    def test_postgresql_skill_expression_compiles_with_bound_parameters(self):
        postgres = DatabaseWrapper({'ENGINE': 'django.db.backends.postgresql', 'NAME': 'compile_only'})
        value = "Python' OR 1=1 --"
        query = User.objects.filter(HabilidadeIExact(F('habilidades'), Value(value))).query
        sql, params = query.get_compiler(connection=postgres).as_sql()
        self.assertIn('jsonb_array_elements', sql)
        self.assertIn("jsonb_typeof(skill.value) = 'string'", sql)
        self.assertNotIn(value, sql)
        self.assertIn(value, params)

    def test_explicit_allowlists(self):
        user = User(id=42, email='private@example.com', name='Private', habilidades=['Private'])
        user.portfolio_publicado = []
        self.assertEqual(
            set(FreelancerPublicoListSerializer(user).data),
            {
                'id',
                'nome',
                'profissao',
                'cidade',
                'habilidades',
                'foto_perfil',
            },
        )
        self.assertEqual(
            set(FreelancerPublicoDetailSerializer(user).data),
            {
                'id',
                'nome',
                'profissao',
                'cidade',
                'habilidades',
                'foto_perfil',
                'descricao',
                'portfolio',
            },
        )

    def test_openapi_exposes_final_routes(self):
        schema = SchemaGenerator(patterns=[path('api/', include(router.urls))]).get_schema(public=True)
        operation = schema['paths']['/api/freelancers/']['get']
        self.assertNotIn('parcial', operation['summary'])
        self.assertTrue({'200', '400', '401', '403'} <= set(operation['responses']))
        self.assertIn('/api/freelancers/{id}/', schema['paths'])
        self.assertTrue(
            {'search', 'profissao', 'habilidade', 'cidade', 'page'}
            <= {parameter['name'] for parameter in operation['parameters']}
        )


class FreelancerPublicoMigrationTests(TransactionTestCase):
    def test_existing_profiles_and_projects_remain_private(self):
        old_target = [('core', '0020_freelance_complementos')]
        new_target = [('core', '0021_publicacao_perfil_portfolio')]
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old_target)
            apps = executor.loader.project_state(old_target).apps
            old_user = apps.get_model('core', 'User').objects.create(
                email='migration-b45@example.com',
                name='Legado',
                localizacao='Endereço privado',
                perfil_configurado=True,
            )
            old_project = apps.get_model('core', 'Portfolio').objects.create(
                usuario_id=old_user.pk,
                titulo='Legado',
                categoria='Design',
                descricao='Privado',
            )
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            migrated_user = User.objects.get(pk=old_user.pk)
            self.assertFalse(migrated_user.perfil_publico)
            self.assertEqual(migrated_user.cidade_publica, '')
            self.assertEqual(migrated_user.localizacao, 'Endereço privado')
            self.assertFalse(Portfolio.objects.get(pk=old_project.pk).publico)
        finally:
            MigrationExecutor(connection).migrate(latest_targets)
