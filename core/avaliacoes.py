"""Atomic operations shared by completion and review endpoints."""

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound
from rest_framework.generics import get_object_or_404

from core.models import Avaliacao, Candidatura, ConclusaoTrabalho
from core.permissions import account_type


class AvaliacaoConflict(APIException):
    status_code = 409
    default_detail = 'A operação não é compatível com o estado atual deste trabalho.'
    default_code = 'avaliacao_conflict'


class AvaliacaoUnavailable(APIException):
    status_code = 503
    default_detail = 'Serviço de avaliações temporariamente indisponível. Tente novamente.'
    default_code = 'avaliacao_unavailable'


def candidatura_do_participante(usuario, candidatura_id, *, lock=False):
    if not 0 < candidatura_id <= 2**63 - 1:
        raise NotFound()
    role = account_type(usuario)
    queryset = Candidatura.objects.select_related('oportunidade', 'oportunidade__empresa', 'freelancer')
    if role == 'empresa':
        queryset = queryset.filter(oportunidade__empresa=usuario)
    elif role == 'usuario':
        queryset = queryset.filter(freelancer=usuario)
    else:
        queryset = queryset.none()
    if lock:
        queryset = queryset.select_for_update(of=('self',))
    return get_object_or_404(queryset, pk=candidatura_id)


def validar_participantes(candidatura):
    empresa = candidatura.oportunidade.empresa
    freelancer = candidatura.freelancer
    if empresa is None or empresa.pk == freelancer.pk:
        raise AvaliacaoConflict('O trabalho não possui dois participantes válidos.')
    if not empresa.is_active or not freelancer.is_active:
        raise AvaliacaoConflict('O trabalho não possui dois participantes válidos.')
    if account_type(empresa) != 'empresa' or account_type(freelancer) != 'usuario':
        raise AvaliacaoConflict('O trabalho não possui dois participantes válidos.')
    if candidatura.status != Candidatura.Status.APROVADA:
        raise AvaliacaoConflict('A candidatura precisa estar aprovada.')


def validar_vinculos(conclusao, candidatura):
    if (
        conclusao.empresa_id != candidatura.oportunidade.empresa_id
        or conclusao.freelancer_id != candidatura.freelancer_id
    ):
        raise AvaliacaoConflict('Os participantes do trabalho foram alterados; as confirmações não são transferíveis.')


def confirmar_conclusao(usuario, candidatura_id):
    try:
        with transaction.atomic():
            candidatura = candidatura_do_participante(usuario, candidatura_id, lock=True)
            validar_participantes(candidatura)
            conclusao, _ = ConclusaoTrabalho.objects.get_or_create(
                candidatura=candidatura,
                defaults={
                    'empresa_id': candidatura.oportunidade.empresa_id,
                    'freelancer_id': candidatura.freelancer_id,
                },
            )
            validar_vinculos(conclusao, candidatura)
            field = 'empresa_confirmou_em' if usuario.pk == conclusao.empresa_id else 'freelancer_confirmou_em'
            # Conditional update preserves the first confirmation, including on SQLite.
            ConclusaoTrabalho.objects.filter(pk=conclusao.pk, **{f'{field}__isnull': True}).update(**{
                field: timezone.now()
            })
            conclusao.refresh_from_db()
            return conclusao
    except (IntegrityError, OperationalError):
        raise AvaliacaoUnavailable() from None


def criar_avaliacao(usuario, *, candidatura_id, nota, comentario=''):
    try:
        with transaction.atomic():
            candidatura = candidatura_do_participante(usuario, candidatura_id, lock=True)
            validar_participantes(candidatura)
            conclusao = ConclusaoTrabalho.objects.filter(candidatura=candidatura).first()
            if conclusao is None or not conclusao.concluido:
                raise AvaliacaoConflict('A empresa e o freelancer precisam confirmar a conclusão do trabalho.')
            validar_vinculos(conclusao, candidatura)
            avaliado_id = conclusao.freelancer_id if usuario.pk == conclusao.empresa_id else conclusao.empresa_id
            return Avaliacao.objects.create(
                candidatura=candidatura,
                avaliador=usuario,
                avaliado_id=avaliado_id,
                nota=nota,
                comentario=comentario,
            )
    except IntegrityError:
        # The database is the arbiter; do not rely on an earlier exists() query.
        raise AvaliacaoConflict(
            'Já existe uma avaliação deste autor para o trabalho ou os dados são inconsistentes.'
        ) from None
    except OperationalError:
        raise AvaliacaoUnavailable() from None
