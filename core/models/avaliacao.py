"""Conclusão bilateral e avaliações vinculadas às candidaturas existentes."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class ConclusaoTrabalho(models.Model):
    candidatura = models.OneToOneField('core.Candidatura', on_delete=models.CASCADE, related_name='conclusao')
    # Preserve the identities that confirmed; a later ownership change is not consent.
    empresa = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    empresa_confirmou_em = models.DateTimeField(null=True, blank=True)
    freelancer_confirmou_em = models.DateTimeField(null=True, blank=True)

    @property
    def concluido(self):
        return self.empresa_confirmou_em is not None and self.freelancer_confirmou_em is not None

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(empresa=F('freelancer')), name='conclusao_participantes_distintos'),
        ]


class AvaliacaoQuerySet(models.QuerySet):
    def validas(self):
        """Fail closed if the underlying conclusion or participant links become invalid."""
        return (
            self
            .filter(
                candidatura__status='aprovada',
                candidatura__conclusao__empresa_confirmou_em__isnull=False,
                candidatura__conclusao__freelancer_confirmou_em__isnull=False,
                candidatura__conclusao__empresa=F('candidatura__oportunidade__empresa'),
                candidatura__conclusao__freelancer=F('candidatura__freelancer'),
                nota__gte=1,
                nota__lte=5,
            )
            .filter(
                Q(avaliador=F('candidatura__conclusao__empresa'), avaliado=F('candidatura__conclusao__freelancer'))
                | Q(avaliador=F('candidatura__conclusao__freelancer'), avaliado=F('candidatura__conclusao__empresa'))
            )
            .exclude(avaliador=F('avaliado'))
        )


class Avaliacao(models.Model):
    candidatura = models.ForeignKey('core.Candidatura', on_delete=models.CASCADE, related_name='avaliacoes')
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='avaliacoes_enviadas'
    )
    avaliado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='avaliacoes_recebidas'
    )
    nota = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(max_length=1000, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = AvaliacaoQuerySet.as_manager()

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            models.UniqueConstraint(fields=['candidatura', 'avaliador'], name='avaliacao_candidatura_autor_unica'),
            models.CheckConstraint(condition=Q(nota__gte=1, nota__lte=5), name='avaliacao_nota_entre_1_e_5'),
            models.CheckConstraint(condition=~Q(avaliador=F('avaliado')), name='avaliacao_participantes_distintos'),
        ]
        indexes = [models.Index(fields=['avaliado', '-criado_em', '-id'], name='avaliacao_recebida_data_idx')]
