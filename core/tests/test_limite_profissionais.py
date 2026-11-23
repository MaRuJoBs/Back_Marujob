from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import Candidatura, Freelance, NotificacaoFreelancer, User


class LimiteProfissionaisTests(APITestCase):
    def test_limite_preserva_decisao_idempotente_e_permite_recusa(self):
        empresa = User.objects.create_user('b62-empresa@example.com')
        empresa.groups.add(Group.objects.get(name='Empresa'))
        vaga = Freelance.objects.create(empresa=empresa, titulo='Design', preco=10, tempo='Livre', max_profissionais=1)
        primeiro = Candidatura.objects.create(
            freelancer=User.objects.create_user('b62-primeiro@example.com'), oportunidade=vaga
        )
        segundo = Candidatura.objects.create(
            freelancer=User.objects.create_user('b62-segundo@example.com'), oportunidade=vaga
        )
        self.client.force_authenticate(empresa)

        aprovar_primeiro = f'/api/candidaturas/{primeiro.pk}/aprovar/'
        self.assertEqual(self.client.post(aprovar_primeiro).status_code, 200)
        self.assertEqual(self.client.post(aprovar_primeiro).status_code, 200)
        bloqueada = self.client.post(f'/api/candidaturas/{segundo.pk}/aprovar/')
        self.assertEqual(bloqueada.status_code, 409)
        self.assertEqual(bloqueada.data['detail'].code, 'oportunidade_limite_atingido')
        self.assertFalse(NotificacaoFreelancer.objects.filter(candidatura=segundo).exists())
        self.assertEqual(self.client.post(f'/api/candidaturas/{segundo.pk}/recusar/').status_code, 200)
        self.assertEqual(NotificacaoFreelancer.objects.filter(candidatura=primeiro).count(), 1)


class LimiteProfissionaisConcurrencyTests(TransactionTestCase):
    def test_aprovacoes_concorrentes_disputam_a_ultima_vaga(self):
        empresa = User.objects.create_user('b58-empresa@example.invalid')
        grupo, _ = Group.objects.get_or_create(name='Empresa')
        empresa.groups.add(grupo)
        vaga = Freelance.objects.create(empresa=empresa, titulo='Design', preco=10, tempo='Livre', max_profissionais=1)
        candidaturas = [
            Candidatura.objects.create(
                freelancer=User.objects.create_user(f'b58-freelancer-{indice}@example.invalid'),
                oportunidade=vaga,
            )
            for indice in range(2)
        ]
        urls = [f'/api/candidaturas/{candidatura.pk}/aprovar/' for candidatura in candidaturas]
        disputou_bloqueio = Event()
        barreira = Barrier(2, action=disputou_bloqueio.set)
        select_for_update = type(Freelance.objects.all()).select_for_update

        def sincronizar_bloqueio(queryset, *args, **kwargs):
            if queryset.model is Freelance:
                barreira.wait(timeout=10)
            return select_for_update(queryset, *args, **kwargs)

        def aprovar(url):
            cliente = APIClient()
            cliente.force_authenticate(empresa)
            try:
                return cliente.post(url).status_code
            finally:
                connections.close_all()

        with patch('core.notificacoes_freelancer.enviar_push') as push:
            with (
                patch('django.db.models.query.QuerySet.select_for_update', sincronizar_bloqueio),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                respostas = list(pool.map(aprovar, urls))

            self.assertTrue(disputou_bloqueio.is_set())
            if connection.vendor == 'sqlite':
                # Contenção do SQLite pode exigir repetição após o fim das duas transações.
                self.assertTrue(set(respostas) <= {200, 409, 503}, respostas)
                self.assertLessEqual(respostas.count(200), 1, respostas)
                respostas = [
                    aprovar(url) if codigo == status.HTTP_503_SERVICE_UNAVAILABLE else codigo
                    for url, codigo in zip(urls, respostas, strict=True)
                ]

            self.assertCountEqual(respostas, [200, 409])
            vencedora = Candidatura.objects.get(oportunidade=vaga, status=Candidatura.Status.APROVADA)
            self.assertEqual(vencedora.pk, candidaturas[respostas.index(200)].pk)
            self.assertEqual(Candidatura.objects.get(pk=candidaturas[respostas.index(409)].pk).status, 'pendente')
            aviso = NotificacaoFreelancer.objects.get(candidatura__oportunidade=vaga)
            self.assertEqual(aviso.candidatura_id, vencedora.pk)
            self.assertEqual(aviso.destinatario_id, vencedora.freelancer_id)
            push.assert_called_once_with(aviso)


class LimiteProfissionaisMigrationTests(TransactionTestCase):
    def test_upgrade_preserva_oportunidade_e_historico(self):
        executor = MigrationExecutor(connection)
        final = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(final))
        anteriores = executor.migrate([('core', '0025_notificacoes_freelancer_push')]).apps
        usuario = anteriores.get_model('core', 'User').objects.create(email='b62-legado@example.com')
        vaga = anteriores.get_model('core', 'Freelance').objects.create(titulo='Legada', preco=10, tempo='Livre')
        candidatura = anteriores.get_model('core', 'Candidatura').objects.create(
            freelancer=usuario, oportunidade=vaga, status='aprovada'
        )
        aviso = anteriores.get_model('core', 'NotificacaoFreelancer').objects.create(
            destinatario=usuario, candidatura=candidatura, evento='candidatura_aprovada', titulo='Aprovada'
        )

        MigrationExecutor(connection).migrate(final)

        self.assertIsNone(Freelance.objects.get(pk=vaga.pk).max_profissionais)
        self.assertTrue(NotificacaoFreelancer.objects.filter(pk=aviso.pk, candidatura_id=candidatura.pk).exists())
