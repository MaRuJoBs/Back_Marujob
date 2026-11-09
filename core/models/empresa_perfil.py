from django.conf import settings
from django.core.validators import URLValidator
from django.db import models

from core.models.freelance import Freelance


class EmpresaPerfil(models.Model):
    empresa = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='empresa_perfil',
    )
    descricao_institucional = models.TextField(max_length=2000, blank=True, default='')
    area_atuacao = models.CharField(max_length=120, blank=True, default='')
    cidade = models.CharField(max_length=100, blank=True, default='')
    uf = models.CharField(max_length=2, choices=Freelance.UF_CHOICES, blank=True, default='')
    website = models.URLField(
        max_length=200,
        blank=True,
        default='',
        validators=[URLValidator(schemes=['http', 'https'])],
    )
    contato_comercial = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f'Perfil institucional {self.empresa_id}'
