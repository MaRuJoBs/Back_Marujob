# Django integration assertions match the existing test suite.
# ruff: noqa: PT009
from datetime import date
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Group
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase

from core.models import Freelance, User
from core.serializers import FreelanceSerializer
from core.views.freelance import FreelanceViewSet

SEARCH_CHARACTER_LIMIT = 200


class OpportunityQueryTests(APITestCase):  # noqa: PLR0904 -- opportunity API integration scenarios
    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('queries-company@example.com', 'password')
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.worker = User.objects.create_user('queries-worker@example.com', 'password')
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.jobs = [
            Freelance.objects.create(
                empresa=cls.company,
                titulo=f'Designer {index}',
                tag='design',
                preco=index * 10,
                tempo='1 dia',
            )
            for index in range(23)
        ]
        cls.other = Freelance.objects.create(
            titulo='Programador',
            descricao='Designer',
            tag='dev',
            preco=500,
            tempo='2 dias',
        )

    def setUp(self):
        self.client.force_authenticate(self.worker)

    def get_list(self, **params):
        response = self.client.get('/api/freelances/', params)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_list_contract_order_and_nulls(self):
        data = self.get_list()
        self.assertEqual(set(data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(data['count'], 24)
        self.assertIsNone(data['previous'])
        self.assertEqual([row['id'] for row in data['results']], [job.pk for job in self.jobs[:10]])
        detail = self.client.get(f'/api/freelances/{self.other.pk}/').data
        self.assertEqual(
            set(detail),
            {
                'id',
                'empresa',
                'titulo',
                'descricao',
                'tag',
                'preco',
                'tempo',
                'requisitos',
                'beneficios',
                'tipo_contratacao',
                'nivel_experiencia',
                'jornada_trabalho',
                'data_publicacao',
                'salario_minimo',
                'salario_maximo',
            },
        )
        self.assertIsNone(detail['empresa'])

    def test_empty_collection(self):
        Freelance.objects.all().delete()
        self.assertEqual(self.get_list(), {'count': 0, 'next': None, 'previous': None, 'results': []})

    def test_search_title(self):
        for query, count in [('Designer 12', 1), ('sign', 23), ('DESIGNER', 23), ('absent', 0), ('', 24)]:
            with self.subTest(query=query):
                self.assertEqual(self.get_list(search=query)['count'], count)

    def test_tag_exact_case_insensitive(self):
        for tag, count in [('design', 23), ('DESIGN', 23), ('des', 0), ('missing', 0), ('', 24)]:
            with self.subTest(tag=tag):
                self.assertEqual(self.get_list(tag=tag)['count'], count)

    def test_search_blank_and_whitespace(self):
        for search, count in [('', 24), ('   ', 24), ('  Designer   12  ', 1)]:
            with self.subTest(search=search):
                self.assertEqual(self.get_list(search=search)['count'], count)

    def test_search_at_limits(self):
        for search in ['x' * 200, ' '.join(['Designer'] * 20)]:
            with self.subTest(search=search):
                data = self.get_list(search=search)
                self.assertEqual(data['count'], 0 if len(search) == SEARCH_CHARACTER_LIMIT else 23)

    def test_search_excessive_characters_rejected_without_queries(self):
        for search in ['x' * 201, ' ' * 201, 'x ' * 1100]:
            with self.subTest(length=len(search)), self.assertNumQueries(0):
                response = self.client.get('/api/freelances/', {'search': search})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {'search': ['A pesquisa deve ter no máximo 200 caracteres.']})

    def test_search_excessive_terms_rejected_without_queries(self):
        for search in [' '.join(['x'] * 21), ','.join(['x'] * 100)]:
            with self.subTest(search=search), self.assertNumQueries(0):
                response = self.client.get('/api/freelances/', {'search': search})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {'search': ['A pesquisa deve ter no máximo 20 termos.']})

    def test_search_quoted_terms_follow_drf_parser(self):
        search = ' '.join(['"Designer 12"'] * 14)
        self.assertEqual(self.get_list(search=search)['count'], 1)
        self.assertEqual(self.get_list(search='Designer,12')['count'], 1)

    def test_search_special_characters_are_literal(self):
        job = Freelance.objects.create(titulo='Designer 100%_especial', preco=0, tempo='1 dia')
        for search in ['%', '_', '%_especial']:
            with self.subTest(search=search):
                data = self.get_list(search=search)
                self.assertEqual(data['count'], 1)
                self.assertEqual(data['results'][0]['id'], job.pk)

    def test_price_bounds_inclusive(self):
        for params, count in [
            ({'preco_min': 200}, 4),
            ({'preco_max': 10}, 2),
            ({'preco_min': 0, 'preco_max': 0}, 1),
            ({'preco_min': 100, 'preco_max': 120}, 3),
        ]:
            with self.subTest(params=params):
                self.assertEqual(self.get_list(**params)['count'], count)

    def test_invalid_query_values(self):
        for name in ['preco_min', 'preco_max']:
            for value in ['invalid', '', '-1', 'NaN', 'Infinity', '1.001', '100000000.00']:
                with self.subTest(name=name, value=value):
                    response = self.client.get('/api/freelances/', {name: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(name, response.data)
        response = self.client.get('/api/freelances/', {'preco_min': 2, 'preco_max': 1})
        self.assertEqual(response.status_code, 400)
        self.assertIn('preco_max', response.data)

    def test_combined_filters_and_pagination(self):
        params = {'search': 'DESIGNER', 'tag': 'design', 'preco_min': 10, 'preco_max': 210}
        first = self.get_list(**params)
        self.assertEqual(first['count'], 21)
        self.assertEqual(len(first['results']), 10)
        second = self.client.get(first['next']).data
        self.assertEqual(second['results'][0]['id'], self.jobs[11].pk)
        self.assertIsNotNone(second['previous'])
        last = self.client.get(second['next']).data
        self.assertEqual([row['id'] for row in last['results']], [self.jobs[21].pk])
        self.assertIsNone(last['next'])
        self.assertEqual(self.client.get(second['previous']).data, first)

    def test_invalid_pages(self):
        for page in ['0', '-1', 'abc', '999']:
            with self.subTest(page=page):
                self.assertEqual(self.client.get('/api/freelances/', {'page': page}).status_code, 404)

    def test_query_does_not_restrict_detail(self):
        response = self.client.get(f'/api/freelances/{self.jobs[0].pk}/', {'search': 'absent', 'preco_min': 'bad'})
        self.assertEqual(response.status_code, 200)

    def test_permissions_with_queries(self):
        url = f'/api/freelances/{self.jobs[0].pk}/'
        self.assertEqual(self.get_list(tag='design')['count'], 23)
        for method in ['post', 'put', 'patch', 'delete']:
            target = '/api/freelances/' if method == 'post' else url
            self.assertEqual(getattr(self.client, method)(target, {}, format='json').status_code, 403)
        self.client.force_authenticate(self.company)
        self.assertEqual(self.get_list(search='Designer')['count'], 23)
        other_company = User.objects.create_user('queries-other@example.com', 'password')
        other_company.groups.add(Group.objects.get(name='Empresa'))
        self.client.force_authenticate(other_company)
        for method in ['put', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)(url, {}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/freelances/', {'tag': 'design'}).status_code, 401)

    def test_each_model_choice_filters_by_exact_value(self):
        for field, choices in [
            ('tipo_contratacao', Freelance.TipoContratacao.values),
            ('nivel_experiencia', Freelance.NivelExperiencia.values),
        ]:
            for value in choices:
                with self.subTest(field=field, value=value):
                    job = Freelance.objects.create(titulo=value, preco=100, tempo='1 dia', **{field: value})
                    data = self.get_list(**{field: value})
                    self.assertEqual(data['count'], 1)
                    self.assertEqual(data['results'], [FreelanceSerializer(job).data])

    def test_valid_choice_without_matches_and_blank_filters(self):
        self.assertEqual(self.get_list(tipo_contratacao='PJ')['count'], 0)
        self.assertEqual(self.get_list(nivel_experiencia='Pleno')['count'], 0)
        self.assertEqual(self.get_list(tipo_contratacao='', nivel_experiencia='', tag='   ')['count'], 24)

    def test_invalid_choices_rejected_before_database_queries(self):
        for field, values in [
            ('tipo_contratacao', ['pj', 'Autonomo', 'Remoto', ' PJ ', 'null']),
            ('nivel_experiencia', ['pleno', 'Junior', 'Diretor', ' ', 'null']),
        ]:
            for value in values:
                with self.subTest(field=field, value=value), self.assertNumQueries(0):
                    response = self.client.get('/api/freelances/', {field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.data)

    def test_all_filters_paginate_without_duplicates_and_preserve_links(self):
        Freelance.objects.filter(tag='design').update(tipo_contratacao='PJ', nivel_experiencia='Pleno')
        Freelance.objects.filter(pk=self.jobs[2].pk).update(tipo_contratacao='CLT')
        Freelance.objects.filter(pk=self.jobs[3].pk).update(nivel_experiencia='Júnior')
        params = {
            'search': 'Designer',
            'tag': 'design',
            'preco_min': '0',
            'preco_max': '220',
            'tipo_contratacao': 'PJ',
            'nivel_experiencia': 'Pleno',
        }
        data = self.get_list(**params)
        ids = []
        page_lengths = []
        while True:
            self.assertEqual(data['count'], 21)
            page_lengths.append(len(data['results']))
            ids.extend(row['id'] for row in data['results'])
            for link in [data['next'], data['previous']]:
                if link:
                    query = parse_qs(urlsplit(link).query)
                    for name, value in params.items():
                        self.assertEqual(query[name], [value])
            if data['next'] is None:
                break
            response = self.client.get(data['next'])
            self.assertEqual(response.status_code, 200)
            data = response.data
        self.assertEqual(page_lengths, [10, 10, 1])
        self.assertEqual(ids, [job.pk for index, job in enumerate(self.jobs) if index not in {2, 3}])
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(self.get_list(**params, page='last')['results'], data['results'])

    def test_repeated_parameters_keep_last_value(self):
        self.jobs[1].tipo_contratacao = 'PJ'
        self.jobs[1].nivel_experiencia = 'Pleno'
        self.jobs[1].save()
        data = self.get_list(
            search=['absent', 'Designer'],
            tag=['dev', 'design'],
            preco_min=['invalid', '10'],
            preco_max=['invalid', '10'],
            tipo_contratacao=['invalid', 'PJ'],
            nivel_experiencia=['invalid', 'Pleno'],
            page=['999', '1'],
        )
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], self.jobs[1].pk)

    def test_unknown_parameters_do_not_change_existing_contract(self):
        data = self.get_list(categoria='inexistente', modalidade='Remoto', status='rascunho', page_size=1)
        self.assertEqual(data['count'], 24)
        self.assertEqual(len(data['results']), 10)

    def test_invalid_tag_length(self):
        with self.assertNumQueries(0):
            response = self.client.get('/api/freelances/', {'tag': 'x' * 51})
        self.assertEqual(response.status_code, 400)
        self.assertIn('tag', response.data)

    def test_accented_search_and_tag_follow_database_matching(self):
        job = Freelance.objects.create(titulo='Projetar árvore urbana', tag='área verde', preco=0, tempo='1 dia')
        data = self.get_list(search='PROJETAR árvore', tag='área verde')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], job.pk)
        self.assertEqual(self.get_list(search='arvore')['count'], 0)

    def test_publication_date_is_metadata_and_nullable_detail_stays_readable(self):
        self.jobs[0].data_publicacao = date(2099, 1, 1)
        self.jobs[0].save()
        self.assertEqual(self.get_list()['count'], 24)
        self.other.tag = None
        self.other.descricao = None
        self.other.save(update_fields=['tag', 'descricao'])
        response = self.client.get(f'/api/freelances/{self.other.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, FreelanceSerializer(self.other).data)
        for field in ['empresa', 'descricao', 'tag', 'data_publicacao', 'salario_minimo', 'salario_maximo']:
            self.assertIsNone(response.data[field])
        for field in ['requisitos', 'beneficios', 'tipo_contratacao', 'nivel_experiencia', 'jornada_trabalho']:
            self.assertEqual(response.data[field], '')

    def test_new_filters_do_not_restrict_detail_or_owner_crud(self):
        params = '?tipo_contratacao=invalid&nivel_experiencia=invalid'
        detail = f'/api/freelances/{self.jobs[0].pk}/{params}'
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.client.force_authenticate(self.company)
        payload = {'titulo': 'Atualizada', 'preco': '15.00', 'tempo': '2 dias'}
        for method in ['put', 'patch']:
            self.assertEqual(getattr(self.client, method)(detail, payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/freelances/{params}', payload, format='json').status_code, 201)
        self.assertEqual(self.client.delete(detail).status_code, 204)

    def test_read_query_count_is_constant(self):
        with self.assertNumQueries(2):
            self.get_list(tag='design')
        with self.assertNumQueries(1):
            response = self.client.get(f'/api/freelances/{self.jobs[0].pk}/')
        self.assertEqual(response.status_code, 200)

    def test_jwt_authentication_for_filtered_list_and_detail(self):
        self.client.force_authenticate(None)
        for actor in [self.worker, self.company]:
            token = self.client.post('/api/token/', {'email': actor.email, 'password': 'password'}, format='json')
            self.assertEqual(token.status_code, 200)
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.data["access"]}')
            self.assertEqual(self.get_list(search='Designer', tag='design')['count'], 23)
            self.assertEqual(self.client.get(f'/api/freelances/{self.jobs[0].pk}/').status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get('/api/freelances/', {'tag': 'design'}).status_code, 401)

    def test_openapi_documents_filters_only_on_list(self):
        patterns = [
            path('api/freelances/', FreelanceViewSet.as_view({'get': 'list'})),
            path('api/freelances/<int:pk>/', FreelanceViewSet.as_view({'get': 'retrieve'})),
        ]
        schema = SchemaGenerator(patterns=patterns).get_schema(public=True)
        operation = schema['paths']['/api/freelances/']['get']
        self.assertEqual(
            {param['name'] for param in operation['parameters']},
            {'search', 'tag', 'preco_min', 'preco_max', 'tipo_contratacao', 'nivel_experiencia', 'page'},
        )
        detail = schema['paths']['/api/freelances/{id}/']['get']
        self.assertEqual({param['name'] for param in detail['parameters']}, {'id'})
