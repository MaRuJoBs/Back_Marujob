# Django unittest assertions follow the existing integration tests.
# ruff: noqa: PT009, PT027
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import OperationalError, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from py_vapid import Vapid
from pywebpush import WebPushException
from requests import Response
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from core.models import Candidatura, Freelance, Notificacao, NotificacaoFreelancer, PushSubscription, User
from core.push_delivery import MAX_DEVICES, PushSession

HISTORICO = '/api/notificacoes-freelancer/'
SUBSCRIPTIONS = '/api/push/subscriptions/'
VAPID_KEY = '/api/push/vapid-public-key/'


def encoded(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def subscription(token='device-one'):
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return {
        'endpoint': f'https://fcm.googleapis.com/fcm/send/{token}',
        'keys': {
            'auth': encoded(b'a' * 16),
            'p256dh': encoded(key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)),
        },
        'expirationTime': None,
    }


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'b60'}})
class NotificacoesFreelancerTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        freelancer_group = Group.objects.get(name='Usuário')
        empresa_group = Group.objects.get(name='Empresa')
        cls.freelancer = User.objects.create_user('b60-freelancer@example.com', telefone='private-phone')
        cls.outro = User.objects.create_user('b60-outro@example.com')
        cls.empresa = User.objects.create_user('b60-empresa@example.com')
        cls.outra_empresa = User.objects.create_user('b60-outra-empresa@example.com')
        cls.freelancer.groups.add(freelancer_group)
        cls.outro.groups.add(freelancer_group)
        cls.empresa.groups.add(empresa_group)
        cls.outra_empresa.groups.add(empresa_group)
        cls.vaga = Freelance.objects.create(empresa=cls.empresa, titulo='Design', preco=100, tempo='Livre')
        cls.outra_vaga = Freelance.objects.create(empresa=cls.empresa, titulo='Pesquisa', preco=100, tempo='Livre')

    def setUp(self):
        cache.clear()

    def login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def candidatar(self, freelancer, vaga):
        self.login(freelancer)
        resposta = self.client.post('/api/candidaturas/', {'oportunidade': vaga.pk}, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta.data['id']

    def decidir(self, candidatura, decisao):
        return self.client.post(f'/api/candidaturas/{candidatura}/{decisao}/')

    def ativar_vapid(self):
        vapid = Vapid()
        vapid.generate_keys()
        private = encoded(vapid.private_key.private_numbers().private_value.to_bytes(32, 'big'))
        public = encoded(vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
        contexto = override_settings(
            VAPID_PUBLIC_KEY=public, VAPID_PRIVATE_KEY=private, VAPID_SUBJECT='mailto:test@example.com'
        )
        self.enterContext(contexto)
        return public

    def cadastrar(self, dados):
        return self.client.post(SUBSCRIPTIONS, dados, format='json')

    def test_aprovacao_idempotente_e_historico_privado(self):
        self.assertEqual(self.client.get(HISTORICO).status_code, 401)
        candidatura = self.candidatar(self.freelancer, self.vaga)
        self.login(self.outra_empresa)
        self.assertEqual(self.decidir(candidatura, 'aprovar').status_code, 404)
        self.login(self.empresa)
        self.assertEqual(self.client.get(HISTORICO).status_code, 403)
        with self.captureOnCommitCallbacks() as callbacks:
            self.assertEqual(self.decidir(candidatura, 'aprovar').status_code, 200)
            self.assertEqual(self.decidir(candidatura, 'aprovar').status_code, 200)
            self.assertEqual(self.decidir(candidatura, 'recusar').status_code, 409)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(Notificacao.objects.filter(candidatura_id=candidatura).count(), 1)
        self.assertEqual(self.client.get('/api/notificacoes/').data['count'], 1)
        self.login(self.freelancer)
        pagina = self.client.get(HISTORICO).data
        self.assertEqual(pagina['count'], 1)
        evento = pagina['results'][0]
        self.assertEqual(
            set(evento), {'id', 'candidatura', 'oportunidade', 'evento', 'titulo', 'mensagem', 'lida', 'criado_em'}
        )
        self.assertEqual(evento['candidatura'], candidatura)
        self.assertEqual(evento['oportunidade'], self.vaga.pk)
        self.assertEqual(evento['evento'], 'candidatura_aprovada')
        self.assertIn('Design', evento['mensagem'])
        self.assertFalse(evento['lida'])
        self.assertNotIn('private-phone', str(evento))
        detalhe = f'{HISTORICO}{evento["id"]}/'
        self.assertEqual(self.client.get(detalhe).status_code, 200)
        self.assertEqual(self.client.patch(detalhe, {'mensagem': 'alterada'}, format='json').status_code, 405)
        self.login(self.outro)
        self.assertEqual(self.client.get(HISTORICO).data['count'], 0)
        self.assertEqual(self.client.get(detalhe).status_code, 404)
        self.assertEqual(self.client.patch(f'{detalhe}marcar-lida/').status_code, 404)

    def test_recusa_leitura_e_contagem_paginada(self):
        primeira = self.candidatar(self.freelancer, self.vaga)
        segunda = self.candidatar(self.freelancer, self.outra_vaga)
        terceira = self.candidatar(self.outro, self.vaga)
        self.login(self.empresa)
        self.assertEqual(self.decidir(primeira, 'aprovar').status_code, 200)
        for candidatura in (segunda, segunda, terceira):
            self.assertEqual(self.decidir(candidatura, 'recusar').status_code, 200)
        self.login(self.freelancer)
        pagina = self.client.get(f'{HISTORICO}?lida=false').data
        self.assertEqual(pagina['count'], 2)
        evento = pagina['results'][0]
        self.assertEqual(evento['evento'], 'candidatura_recusada')
        self.assertIn('não foi selecionada', evento['mensagem'])
        for _ in range(2):
            resposta = self.client.patch(f'{HISTORICO}{evento["id"]}/marcar-lida/')
            self.assertTrue(resposta.data['lida'])
        self.assertEqual(self.client.get(f'{HISTORICO}?lida=true').data['count'], 1)
        self.assertEqual(self.client.get(f'{HISTORICO}?lida=invalido').status_code, 400)
        self.assertEqual(self.client.post(f'{HISTORICO}marcar-todas-lidas/').data, {'atualizadas': 1})
        self.assertEqual(self.client.post(f'{HISTORICO}marcar-todas-lidas/').data, {'atualizadas': 0})
        self.assertEqual(self.client.get(HISTORICO).data['count'], 2)
        self.assertEqual(self.client.get(f'{HISTORICO}?lida=false').data['count'], 0)
        self.login(self.outro)
        self.assertEqual(self.client.get(f'{HISTORICO}?lida=false').data['count'], 1)

    def test_historico_preserva_evento_quando_candidatura_e_excluida(self):
        candidatura = self.candidatar(self.freelancer, self.vaga)
        self.login(self.empresa)
        self.assertEqual(self.decidir(candidatura, 'aprovar').status_code, 200)
        Candidatura.objects.filter(pk=candidatura).delete()
        self.login(self.freelancer)
        evento = self.client.get(HISTORICO).data['results'][0]
        self.assertIsNone(evento['candidatura'])
        self.assertIsNone(evento['oportunidade'])
        self.assertIn('Design', evento['mensagem'])

    def test_falha_ao_persistir_reverte_decisao_e_callback(self):
        candidatura = self.candidatar(self.freelancer, self.vaga)
        self.login(self.empresa)
        with (
            patch('core.notificacoes_freelancer.NotificacaoFreelancer.objects.create', side_effect=OperationalError),
            self.captureOnCommitCallbacks() as callbacks,
        ):
            self.assertEqual(self.decidir(candidatura, 'aprovar').status_code, 503)
        self.assertEqual(callbacks, [])
        self.assertEqual(Candidatura.objects.get(pk=candidatura).status, Candidatura.Status.PENDENTE)
        self.assertFalse(NotificacaoFreelancer.objects.exists())

    def test_subscription_autenticada_transferencia_e_exclusao(self):
        chave = self.ativar_vapid()
        self.assertEqual(self.client.get(VAPID_KEY).data, {'publicKey': chave})
        dados = subscription()
        self.assertEqual(self.cadastrar(dados).status_code, 401)
        self.login(self.empresa)
        self.assertEqual(self.cadastrar(dados).status_code, 403)
        self.login(self.freelancer)
        resposta = self.cadastrar({**dados, 'usuario': self.outro.pk})
        self.assertEqual(resposta.status_code, 204, resposta.data)
        self.assertEqual(resposta.content, b'')
        self.assertEqual(PushSubscription.objects.get().usuario, self.freelancer)
        self.assertEqual(self.cadastrar(dados).status_code, 204)
        self.login(self.outro)
        endpoint = {'endpoint': dados['endpoint']}
        self.assertEqual(self.client.delete(SUBSCRIPTIONS, endpoint, format='json').status_code, 204)
        self.assertEqual(PushSubscription.objects.get().usuario, self.freelancer)
        self.assertEqual(self.cadastrar({**subscription(), **endpoint}).status_code, 400)
        self.assertEqual(self.cadastrar(dados).status_code, 204)
        self.assertEqual(PushSubscription.objects.get().usuario, self.outro)
        self.assertEqual(self.client.delete(SUBSCRIPTIONS, endpoint, format='json').status_code, 204)
        self.assertFalse(PushSubscription.objects.exists())

    def test_throttle_limita_escritas_por_conta(self):
        self.ativar_vapid()
        self.login(self.freelancer)
        dados = subscription()
        for _ in range(20):
            self.assertEqual(self.cadastrar(dados).status_code, 204)
        resposta = self.cadastrar(dados)
        self.assertEqual(resposta.status_code, 429)
        self.assertIn('Retry-After', resposta.headers)
        self.login(self.outro)
        self.assertEqual(self.cadastrar(subscription('segundo-usuario')).status_code, 204)

    def test_validacao_limite_e_expiracao(self):
        self.ativar_vapid()
        self.login(self.freelancer)
        dados = subscription()
        for endpoint in (
            'http://fcm.googleapis.com/fcm/send/teste',
            'https://127.0.0.1/fcm/send/teste',
            'https://fcm.googleapis.com@127.0.0.1/fcm/send/teste',
            'https://fcm.googleapis.com/fcm/send/%2e%2e',
            'https://fcm.googleapis.com/fcm/send/..',
            'https://fcm.googleapis.com/fcm/send/teste?redirect=x',
        ):
            self.assertEqual(self.cadastrar({**dados, 'endpoint': endpoint}).status_code, 400)
        self.assertEqual(self.cadastrar({**dados, 'keys': {'auth': 'x', 'p256dh': 'x'}}).status_code, 400)
        self.assertEqual(self.cadastrar({**dados, 'expirationTime': 1}).status_code, 400)
        for i in range(MAX_DEVICES):
            self.assertEqual(self.cadastrar(subscription(f'device-{i}')).status_code, 204)
        self.assertEqual(self.cadastrar(dados).status_code, 400)
        self.assertEqual(PushSubscription.objects.count(), MAX_DEVICES)

    def test_push_em_varios_dispositivos_e_falhas_apos_commit(self):
        self.ativar_vapid()
        candidatura = self.candidatar(self.freelancer, self.vaga)
        for nome in ('indisponivel', 'revogado', 'ativo', 'expirado'):
            self.assertEqual(self.cadastrar(subscription(nome)).status_code, 204)
        PushSubscription.objects.filter(endpoint__endswith='/expirado').update(
            expira_em=timezone.now() - timedelta(seconds=1)
        )
        self.login(self.outro)
        self.assertEqual(self.cadastrar(subscription('outra-conta')).status_code, 204)
        self.login(self.empresa)
        revogado = Response()
        revogado.status_code = 410
        revogado._content_consumed = True
        sucesso = Response()
        sucesso.status_code = 201
        sucesso._content_consumed = True
        with (
            patch(
                'core.push_delivery.webpush',
                side_effect=[Timeout('segredo'), WebPushException('segredo', response=revogado), sucesso],
            ) as envio,
            self.assertLogs('core.push_delivery', 'WARNING') as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resposta = self.decidir(candidatura, 'aprovar')
            envio.assert_not_called()
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('segredo', str(logs.output))
        self.assertEqual(Candidatura.objects.get(pk=candidatura).status, Candidatura.Status.APROVADA)
        notificacao = NotificacaoFreelancer.objects.get(candidatura_id=candidatura)
        self.assertEqual(envio.call_count, 3)
        self.assertEqual(PushSubscription.objects.filter(usuario=self.freelancer).count(), 2)
        for chamada in envio.call_args_list:
            payload = json.loads(chamada.kwargs['data'])
            self.assertEqual(
                payload,
                {
                    'event': 'candidatura_aprovada',
                    'notification_id': notificacao.pk,
                    'title': 'Candidatura aprovada!',
                    'body': 'Sua candidatura foi aprovada.',
                    'url': '/notificacoes',
                },
            )

    def test_chave_publica_inconsistente_nao_expoe_configuracao(self):
        self.ativar_vapid()
        with override_settings(VAPID_PUBLIC_KEY='configuracao-invalida'):
            resposta = self.client.get(VAPID_KEY)
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn('configuracao-invalida', str(resposta.data))

    def test_push_assinado_e_cifrado_com_transporte_mockado(self):
        public_key = self.ativar_vapid()
        candidatura = self.candidatar(self.freelancer, self.vaga)
        dispositivo = subscription()
        self.assertEqual(self.cadastrar(dispositivo).status_code, 204)
        self.login(self.empresa)
        resposta_push = Response()
        resposta_push.status_code = 201
        resposta_push._content = b''
        resposta_push._content_consumed = True
        with (
            patch('requests.Session.post', return_value=resposta_push) as post,
            self.assertNoLogs('core.push_delivery', 'WARNING'),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertEqual(self.decidir(candidatura, 'recusar').status_code, 200)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], dispositivo['endpoint'])
        headers = {key.lower(): value for key, value in post.call_args.kwargs['headers'].items()}
        self.assertIn(f'k={public_key}', headers['authorization'])
        self.assertEqual(headers['content-encoding'], 'aes128gcm')
        self.assertNotIn(b'candidatura_recusada', post.call_args.kwargs['data'])
        self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_transporte_bloqueia_redirecionamento(self):
        resposta = Response()
        resposta.status_code = 307
        resposta.headers['Location'] = 'https://invalid.example/'
        with PushSession() as sessao, patch('requests.Session.post', return_value=resposta) as post:
            with self.assertRaises(WebPushException):
                sessao.post('https://fcm.googleapis.com/fcm/send/token', timeout=2)
            self.assertIsNone(sessao.get_redirect_target(resposta))
        self.assertFalse(post.call_args.kwargs['allow_redirects'])


class NotificacaoDecisaoConcorrenteTests(APITransactionTestCase):
    def test_decisoes_opostas_geram_um_unico_evento(self):
        freelancer = User.objects.create_user('b60-concorrente@example.com')
        empresa = User.objects.create_user('b60-decisora@example.com')
        grupo, _ = Group.objects.get_or_create(name='Empresa')
        empresa.groups.add(grupo)
        vaga = Freelance.objects.create(empresa=empresa, titulo='Concorrência', preco=10, tempo='Livre')
        candidatura = Candidatura.objects.create(freelancer=freelancer, oportunidade=vaga)
        url = f'/api/candidaturas/{candidatura.pk}/'
        barreira = Barrier(2)

        def decidir(acao):
            try:
                cliente = APIClient()
                cliente.force_authenticate(empresa)
                barreira.wait(timeout=10)
                return cliente.post(f'{url}{acao}/').status_code
            finally:
                connections.close_all()

        with patch('core.notificacoes_freelancer.enviar_push') as push:
            with ThreadPoolExecutor(max_workers=2) as pool:
                respostas = list(pool.map(decidir, ('aprovar', 'recusar')))
            self.assertLessEqual(respostas.count(200), 1, respostas)
            self.assertTrue(set(respostas) <= {200, 409, 503}, respostas)
            self.client.force_authenticate(empresa)
            if status.HTTP_200_OK not in respostas:
                # SQLite may require a sequential retry when both readers contend for a write.
                self.assertEqual(self.client.post(f'{url}aprovar/').status_code, 200)
        candidatura.refresh_from_db()
        notificacao = NotificacaoFreelancer.objects.get(candidatura=candidatura)
        self.assertEqual(notificacao.destinatario, freelancer)
        self.assertEqual(notificacao.evento, f'candidatura_{candidatura.status}')
        push.assert_called_once_with(notificacao)


class NotificacaoMigrationTests(TransactionTestCase):
    def test_upgrade_a_partir_da_dev_preserva_dados_sem_backfill(self):
        anterior = [('core', '0024_empresaperfil_bairro')]
        atual = [('core', '0025_notificacoes_freelancer_push')]
        executor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(atual))
        modelos = executor.migrate(anterior).apps
        usuario = modelos.get_model('core', 'User')
        vaga_model = modelos.get_model('core', 'Freelance')
        candidatura_model = modelos.get_model('core', 'Candidatura')
        notificacao_model = modelos.get_model('core', 'Notificacao')
        freelancer = usuario.objects.create(email='migration-freelancer@example.com')
        empresa = usuario.objects.create(email='migration-empresa@example.com')
        vaga = vaga_model.objects.create(empresa=empresa, titulo='Histórica', preco=10, tempo='Livre')
        candidatura = candidatura_model.objects.create(freelancer=freelancer, oportunidade=vaga, status='aprovada')
        aviso = notificacao_model.objects.create(empresa=empresa, candidatura=candidatura)

        MigrationExecutor(connection).migrate(atual)

        self.assertTrue(Candidatura.objects.filter(pk=candidatura.pk, status=Candidatura.Status.APROVADA).exists())
        self.assertTrue(Notificacao.objects.filter(pk=aviso.pk, candidatura_id=candidatura.pk).exists())
        self.assertFalse(NotificacaoFreelancer.objects.exists())
        self.assertFalse(PushSubscription.objects.exists())
