from django.conf import settings
from django.db import models


class NotificacaoFreelancer(models.Model):
    class Evento(models.TextChoices):
        APROVADA = 'candidatura_aprovada', 'Candidatura aprovada'
        RECUSADA = 'candidatura_recusada', 'Candidatura recusada'

    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    candidatura = models.OneToOneField('core.Candidatura', null=True, on_delete=models.SET_NULL)
    evento = models.CharField(max_length=20, choices=Evento.choices)
    titulo = models.CharField(max_length=100)
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['destinatario', '-criado_em', '-id'], name='notif_free_historico_idx'),
            models.Index(fields=['destinatario', 'lida', '-criado_em', '-id'], name='notif_free_leitura_idx'),
        ]
