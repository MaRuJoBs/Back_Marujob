from django.conf import settings
from django.db import models


class Candidatura(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        APROVADA = 'aprovada', 'Aprovada'
        RECUSADA = 'recusada', 'Recusada'

    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidaturas')
    oportunidade = models.ForeignKey('core.Freelance', on_delete=models.CASCADE, related_name='candidaturas')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['freelancer', 'oportunidade'], name='candidatura_freelancer_oportunidade_unica'
            ),
        ]
