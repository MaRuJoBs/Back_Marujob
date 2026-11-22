from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

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
