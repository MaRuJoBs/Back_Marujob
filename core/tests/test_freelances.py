from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from core.models import Favorito, Freelance, User
from core.serializers import FreelanceSerializer


class FreelanceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = User.objects.create_user('company34@example.com', 'test-password')
        cls.company.groups.add(Group.objects.get(name='Empresa'))
        cls.other = User.objects.create_user('other34@example.com', 'test-password')
        cls.other.groups.add(Group.objects.get(name='Empresa'))
        cls.job = Freelance.objects.create(empresa=cls.company, titulo='Vaga', preco='100.00', tempo='1 dia')

    def setUp(self):
        self.client.force_authenticate(self.company)
        self.url = f'/api/freelances/{self.job.pk}/'
        self.data = {'titulo': 'Nova vaga', 'preco': '150.00', 'tempo': '2 dias'}

    def test_details(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, FreelanceSerializer(self.job).data)

    def test_missing_opportunity(self):
        self.assertEqual(self.client.get('/api/freelances/999999/').status_code, 404)

    def test_pagination(self):
        for index in range(10):
            Freelance.objects.create(empresa=self.company, titulo=f'Vaga {index}', preco=0, tempo='1 dia')
        response = self.client.get('/api/freelances/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['results'][0]['id'], self.job.pk)
        self.assertIsNotNone(response.data['next'])
        second = self.client.get('/api/freelances/', {'page': 2})
        self.assertEqual(len(second.data['results']), 1)
        self.assertIsNone(second.data['next'])

    def test_unauthenticated_methods(self):
        self.client.force_authenticate(user=None)
        for method, url in [('get', '/api/freelances/'), ('get', self.url),
                            ('post', '/api/freelances/'), ('put', self.url),
                            ('patch', self.url), ('delete', self.url)]:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, self.data, format='json')
                self.assertEqual(response.status_code, 401)
        self.job.refresh_from_db()
        self.assertEqual(self.job.titulo, 'Vaga')
        self.assertEqual(Freelance.objects.count(), 1)

    def test_negative_price_rejected_on_create_and_updates(self):
        for method, url in [('post', '/api/freelances/'), ('put', self.url), ('patch', self.url)]:
            with self.subTest(method=method):
                response = getattr(self.client, method)(url, {**self.data, 'preco': '-0.01'}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('preco', response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.preco, Decimal('100.00'))
        self.assertEqual(Freelance.objects.count(), 1)

    def test_zero_and_decimal_limits(self):
        for price in ['0.00', '99999999.99']:
            with self.subTest(price=price):
                response = self.client.post('/api/freelances/', {**self.data, 'preco': price}, format='json')
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data['preco'], price)
        for price in ['100000000.00', '1.001', 'invalid']:
            with self.subTest(price=price):
                response = self.client.post('/api/freelances/', {**self.data, 'preco': price}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('preco', response.data)

    def test_required_fields_on_create_and_put(self):
        for field in ['titulo', 'preco', 'tempo']:
            for value in ['missing', None, '']:
                data = dict(self.data)
                if value == 'missing':
                    data.pop(field)
                else:
                    data[field] = value
                for method, url in [('post', '/api/freelances/'), ('put', self.url)]:
                    with self.subTest(field=field, value=value, method=method):
                        response = getattr(self.client, method)(url, data, format='json')
                        self.assertEqual(response.status_code, 400)
                        self.assertIn(field, response.data)

    def test_patch_preserves_omitted_fields_and_owner(self):
        response = self.client.patch(self.url, {'titulo': 'Atualizada', 'empresa': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.titulo, 'Atualizada')
        self.assertEqual(self.job.preco, Decimal('100.00'))
        self.assertEqual(self.job.tempo, '1 dia')
        self.assertEqual(self.job.empresa, self.company)

    def test_owner_in_create_and_put_cannot_be_forged(self):
        response = self.client.post('/api/freelances/', {**self.data, 'empresa': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['empresa'], self.company.pk)
        response = self.client.put(self.url, {**self.data, 'empresa': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.empresa, self.company)

    def test_legacy_opportunity_is_readable_but_cannot_be_changed(self):
        legacy = Freelance.objects.create(titulo='Antiga', preco=0, tempo='1 dia')
        url = f'/api/freelances/{legacy.pk}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        for method in ['put', 'patch', 'delete']:
            with self.subTest(method=method):
                response = getattr(self.client, method)(url, self.data, format='json')
                self.assertEqual(response.status_code, 403)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.empresa)
        self.assertEqual(legacy.titulo, 'Antiga')

    def test_deleting_company_preserves_opportunity_and_favorites(self):
        favorite = Favorito.objects.create(usuario=self.other, oportunidade=self.job)
        self.company.delete()
        self.job.refresh_from_db()
        self.assertIsNone(self.job.empresa)
        self.assertEqual(self.job.titulo, 'Vaga')
        self.assertTrue(Favorito.objects.filter(pk=favorite.pk).exists())
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.patch(self.url, {'titulo': 'Forbidden'}, format='json').status_code, 403)

    def test_favorites_share_opportunity_contract(self):
        response = self.client.post('/api/favoritos/', {'oportunidade': self.job.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['oportunidade_detalhes'], self.client.get(self.url).data)
        self.client.patch(self.url, {'preco': '0.00'}, format='json')
        response = self.client.get('/api/favoritos/')
        self.job.refresh_from_db()
        self.assertEqual(response.data['results'][0]['oportunidade_detalhes'], FreelanceSerializer(self.job).data)
