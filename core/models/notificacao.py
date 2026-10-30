from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    empresa = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes')
    candidatura = models.OneToOneField('core.Candidatura', on_delete=models.CASCADE, related_name='notificacao')
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [models.Index(fields=['empresa', 'lida', '-criado_em'], name='notif_empresa_leitura_idx')]
