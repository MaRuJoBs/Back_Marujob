from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Freelance(models.Model):
    class TipoContratacao(models.TextChoices):
        CLT = 'CLT', 'CLT'
        PJ = 'PJ', 'PJ'
        AUTONOMO = 'Autônomo', 'Autônomo'
        TEMPORARIO = 'Temporário', 'Temporário'
        ESTAGIO = 'Estágio', 'Estágio'
        OUTROS = 'Outros', 'Outros'

    class NivelExperiencia(models.TextChoices):
        INICIANTE = 'Iniciante', 'Iniciante'
        JUNIOR = 'Júnior', 'Júnior'
        PLENO = 'Pleno', 'Pleno'
        SENIOR = 'Sênior', 'Sênior'
        ESPECIALISTA = 'Especialista', 'Especialista'

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
    requisitos = models.TextField(max_length=1000, blank=True, default='')
    beneficios = models.TextField(max_length=1000, blank=True, default='')
    tipo_contratacao = models.CharField(max_length=20, choices=TipoContratacao.choices, blank=True, default='')
    nivel_experiencia = models.CharField(max_length=20, choices=NivelExperiencia.choices, blank=True, default='')
    jornada_trabalho = models.CharField(max_length=100, blank=True, default='')
    data_publicacao = models.DateField(blank=True, null=True)
    salario_minimo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    salario_maximo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0'))],
    )

    def __str__(self):
        return self.titulo
