from django.db import transaction

from core.models import Candidatura, NotificacaoFreelancer
from core.push_delivery import enviar_push


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
    transaction.on_commit(lambda: enviar_push(notificacao), robust=True)
