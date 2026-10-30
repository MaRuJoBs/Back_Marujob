from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from core.models import Freelance, User


class OpportunityQueryTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('queries-company@example.com', 'password')
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.worker = User.objects.create_user('queries-worker@example.com', 'password')
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        cls.jobs = [
            Freelance.objects.create(
                empresa=cls.company, titulo=f'Designer {index}', tag='design',
                preco=index * 10, tempo='1 dia',
            ) for index in range(23)
        ]
        cls.other = Freelance.objects.create(
            titulo='Programador', descricao='Designer', tag='dev', preco=500, tempo='2 dias',
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
        self.assertEqual(set(detail), {'id', 'empresa', 'titulo', 'descricao', 'tag', 'preco', 'tempo'})
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
                self.assertEqual(data['count'], 0 if len(search) == 200 else 23)

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
        for params, count in [({'preco_min': 200}, 4), ({'preco_max': 10}, 2),
                              ({'preco_min': 0, 'preco_max': 0}, 1),
                              ({'preco_min': 100, 'preco_max': 120}, 3)]:
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
