from django.conf import settings
from django.db import models


class Favorito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favoritos')
    oportunidade = models.ForeignKey('core.Freelance', on_delete=models.CASCADE, related_name='favoritos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'oportunidade'], name='favorito_usuario_oportunidade_unico'),
        ]
