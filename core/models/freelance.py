from django.conf import settings
from django.db import models


class Freelance(models.Model):
    empresa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='oportunidades',
    )
    titulo = models.CharField(max_length=100)
    descricao = models.TextField(max_length=200, blank=True, null=True)
    tag = models.CharField(max_length=50, blank=True, null=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    tempo = models.CharField(max_length=50)

    def __str__(self):
        return self.titulo
