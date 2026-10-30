from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from core.models import Favorito, Freelance


class FavoritosTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(email='a@example.com', password='senha-teste-123')
        cls.outro = get_user_model().objects.create_user(email='b@example.com', password='senha-teste-456')
        cls.oportunidade = Freelance.objects.create(titulo='Vaga', preco='100.00', tempo='2 dias')
        cls.url = reverse('favoritos-list')

    def setUp(self):
        self.client.force_authenticate(self.usuario)

    def criar(self, usuario=None):
        return Favorito.objects.create(usuario=usuario or self.usuario, oportunidade=self.oportunidade)

    def detalhe(self, favorito):
        return reverse('favoritos-detail', args=[favorito.pk])

    def test_sem_autenticacao(self):
        favorito = self.criar()
        self.client.force_authenticate(user=None)
        for metodo, url, dados in [
            ('get', self.url, {}),
            ('post', self.url, {'oportunidade': self.oportunidade.pk}),
            ('delete', self.detalhe(favorito), {}),
        ]:
            with self.subTest(metodo=metodo):
                self.assertEqual(getattr(self.client, metodo)(url, dados, format='json').status_code, 401)
        self.assertEqual(Favorito.objects.count(), 1)

    def test_criar_persiste_e_reutiliza_serializer(self):
        resposta = self.client.post(self.url, {'oportunidade': self.oportunidade.pk}, format='json')
        self.assertEqual(resposta.status_code, 201)
        favorito = Favorito.objects.get(pk=resposta.data['id'])
        self.assertEqual(favorito.usuario, self.usuario)
        self.assertEqual(favorito.oportunidade, self.oportunidade)
        self.assertIsNotNone(favorito.criado_em)
        self.assertEqual(resposta.data['oportunidade_detalhes']['titulo'], 'Vaga')
        self.assertNotIn('usuario', resposta.data)

    def test_proprietario_enviado_nao_e_utilizado(self):
        resposta = self.client.post(self.url, {
            'oportunidade': self.oportunidade.pk, 'usuario': self.outro.pk,
        }, format='json')
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(Favorito.objects.get().usuario, self.usuario)

    def test_dados_invalidos(self):
        for dados in [{}, {'oportunidade': None}, {'oportunidade': 'invalido'}, {'oportunidade': 999999}]:
            with self.subTest(dados=dados):
                resposta = self.client.post(self.url, dados, format='json')
                self.assertEqual(resposta.status_code, 400)
                self.assertIn('oportunidade', resposta.data)
        self.assertFalse(Favorito.objects.exists())

    def test_post_repetido_retorna_mesmo_favorito(self):
        dados = {'oportunidade': self.oportunidade.pk}
        primeira = self.client.post(self.url, dados, format='json')
        segunda = self.client.post(self.url, dados, format='json')
        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primeira.data, segunda.data)
        self.assertEqual(Favorito.objects.count(), 1)

    def test_constraint_banco_impede_duplicidade(self):
        self.criar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar()
        self.assertEqual(Favorito.objects.count(), 1)

    def test_usuarios_diferentes_favoritam_mesma_oportunidade(self):
        self.criar()
        self.client.force_authenticate(self.outro)
        resposta = self.client.post(self.url, {'oportunidade': self.oportunidade.pk}, format='json')
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(Favorito.objects.count(), 2)

    def test_listas_isoladas_e_ids_cliente_ignorados(self):
        meu = self.criar()
        outro = self.criar(self.outro)
        resposta = self.client.get(self.url, {'usuario': self.outro.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['count'], 1)
        self.assertEqual([item['id'] for item in resposta.data['results']], [meu.pk])
        self.client.force_authenticate(self.outro)
        resposta = self.client.get(self.url)
        self.assertEqual([item['id'] for item in resposta.data['results']], [outro.pk])

    def test_lista_vazia(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data, {'count': 0, 'next': None, 'previous': None, 'results': []})

    def test_paginacao(self):
        for indice in range(11):
            oportunidade = Freelance.objects.create(titulo=f'Vaga {indice}', preco='1.00', tempo='1 dia')
            Favorito.objects.create(usuario=self.usuario, oportunidade=oportunidade)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.data['count'], 11)
        self.assertEqual(len(resposta.data['results']), 10)
        self.assertIsNotNone(resposta.data['next'])
        self.assertEqual(len(self.client.get(self.url, {'page': 2}).data['results']), 1)

    def test_remover_proprio_preserva_oportunidade(self):
        favorito = self.criar()
        resposta = self.client.delete(self.detalhe(favorito))
        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Favorito.objects.exists())
        self.assertTrue(Freelance.objects.filter(pk=self.oportunidade.pk).exists())

    def test_remover_terceiro_bloqueado(self):
        favorito = self.criar(self.outro)
        self.assertEqual(self.client.delete(self.detalhe(favorito)).status_code, 404)
        self.assertTrue(Favorito.objects.filter(pk=favorito.pk).exists())

    def test_remover_inexistente(self):
        self.assertEqual(self.client.delete(reverse('favoritos-detail', args=[999999])).status_code, 404)

    def test_atualizacao_nao_permitida(self):
        favorito = self.criar()
        for metodo in ['put', 'patch']:
            with self.subTest(metodo=metodo):
                resposta = getattr(self.client, metodo)(self.detalhe(favorito), {'usuario': self.outro.pk})
                self.assertEqual(resposta.status_code, 405)
        favorito.refresh_from_db()
        self.assertEqual(favorito.usuario, self.usuario)

    def test_persistencia_apos_logout_e_novo_login_jwt(self):
        cliente = APIClient()
        credenciais = {'email': self.usuario.email, 'password': 'senha-teste-123'}
        token = cliente.post(reverse('token_obtain_pair'), credenciais, format='json')
        self.assertEqual(token.status_code, 200)
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        resposta = cliente.post(self.url, {'oportunidade': self.oportunidade.pk}, format='json')
        self.assertEqual(resposta.status_code, 201)
        favorito_id = resposta.data['id']
        cliente.credentials()
        cliente.logout()
        self.assertEqual(cliente.get(self.url).status_code, 401)
        self.assertTrue(Favorito.objects.filter(pk=favorito_id).exists())
        dispositivo = APIClient()
        token = dispositivo.post(reverse('token_obtain_pair'), credenciais, format='json')
        self.assertEqual(token.status_code, 200)
        dispositivo.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        resposta = dispositivo.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([item['id'] for item in resposta.data['results']], [favorito_id])

    def test_cascade_usuario_e_oportunidade(self):
        favorito = self.criar()
        self.oportunidade.delete()
        self.assertFalse(Favorito.objects.filter(pk=favorito.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.usuario.pk).exists())
        oportunidade = Freelance.objects.create(titulo='Outra', preco='1.00', tempo='1 dia')
        favorito = Favorito.objects.create(usuario=self.usuario, oportunidade=oportunidade)
        self.usuario.delete()
        self.assertFalse(Favorito.objects.filter(pk=favorito.pk).exists())
        self.assertTrue(Freelance.objects.filter(pk=oportunidade.pk).exists())
