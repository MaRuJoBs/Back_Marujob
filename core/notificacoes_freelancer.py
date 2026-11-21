from django.db import transaction

from core.models import Candidatura, NotificacaoFreelancer
from core.push_delivery import enviar_push
from core.webpush import send_web_push


def registrar_decisao(candidatura, status):
    oportunidade = candidatura.oportunidade.titulo
    if status == Candidatura.Status.APROVADA:
        evento = NotificacaoFreelancer.Evento.APROVADA
        titulo = 'Candidatura aprovada!'
        mensagem = f"Parabéns! Sua candidatura para a oportunidade '{oportunidade}' foi aprovada."
    else:
        evento = NotificacaoFreelancer.Evento.RECUSADA
        titulo = 'Candidatura recusada'
        mensagem = f"Sua candidatura para a oportunidade '{oportunidade}' não foi selecionada."

    notificacao = NotificacaoFreelancer.objects.create(
        destinatario_id=candidatura.freelancer_id,
        candidatura=candidatura,
        evento=evento,
        titulo=titulo,
        mensagem=mensagem,
    )

    def entregar_notificacoes():
        enviar_push(notificacao)
        send_web_push(
            candidatura.freelancer_id,
            'Candidatura atualizada',
            f'Sua candidatura para {oportunidade} foi {status}.',
            '/minhas-candidaturas',
        )

    transaction.on_commit(entregar_notificacoes, robust=True)
