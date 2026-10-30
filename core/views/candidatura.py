from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.models import Candidatura, Notificacao
from core.permissions import CandidaturaPermission
from core.serializers.candidatura import (
    CandidaturaCreateSerializer,
    CandidaturaEmpresaSerializer,
    CandidaturaFilterSerializer,
    CandidaturaSerializer,
)


class CandidaturaUnavailable(APIException):
    status_code = 503
    default_detail = 'Serviço de candidaturas temporariamente indisponível. Tente novamente.'
    default_code = 'candidatura_unavailable'


class CandidaturaConflict(APIException):
    status_code = 409
    default_detail = 'A candidatura já foi analisada e não pode receber outra decisão.'
    default_code = 'candidatura_status_conflict'


class CandidaturaViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    permission_classes = [CandidaturaPermission]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return CandidaturaCreateSerializer
        return (
            CandidaturaEmpresaSerializer if getattr(self, 'account_role', None) == 'empresa' else CandidaturaSerializer
        )

    def get_queryset(self):
        queryset = Candidatura.objects.select_related('freelancer', 'oportunidade', 'oportunidade__empresa')
        role = getattr(self, 'account_role', None)
        if role == 'usuario':
            queryset = queryset.filter(freelancer=self.request.user)
        elif role == 'empresa':
            queryset = queryset.filter(oportunidade__empresa=self.request.user)
        else:
            return queryset.none()
        if self.action in {'aprovar', 'recusar'}:
            return queryset
        filters = CandidaturaFilterSerializer(data=self.request.query_params.dict())
        filters.is_valid(raise_exception=True)
        return queryset.filter(**filters.validated_data)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                candidatura = serializer.save(freelancer=self.request.user, status=Candidatura.Status.PENDENTE)
                # Ownerless legacy opportunities retain the FEAT-41 creation contract.
                empresa_id = candidatura.oportunidade.empresa_id
                if empresa_id is not None:
                    Notificacao.objects.get_or_create(candidatura=candidatura, defaults={'empresa_id': empresa_id})
        except IntegrityError:
            duplicate = Candidatura.objects.filter(
                freelancer=self.request.user,
                oportunidade=serializer.validated_data['oportunidade'],
            ).exists()
            message = (
                'Você já se candidatou a esta oportunidade.'
                if duplicate
                else 'Não foi possível registrar a candidatura.'
            )
            raise ValidationError({'oportunidade': [message]}) from None
        except OperationalError:
            # Includes SQLite writer contention; retry after rollback, without leaking SQL.
            raise CandidaturaUnavailable() from None

    def decidir(self, status):
        try:
            with transaction.atomic():
                # Lock only the application: PostgreSQL disallows locking a nullable outer join.
                queryset = Candidatura.objects.filter(oportunidade__empresa=self.request.user)
                candidatura = get_object_or_404(queryset.select_for_update(of=('self',)), pk=self.kwargs['pk'])
                self.check_object_permissions(self.request, candidatura)
                if candidatura.status != status:
                    if candidatura.status != Candidatura.Status.PENDENTE:
                        raise CandidaturaConflict()
                    # Compare-and-set also protects SQLite, where SELECT FOR UPDATE is ignored.
                    changed = queryset.filter(pk=candidatura.pk, status=Candidatura.Status.PENDENTE).update(
                        status=status, atualizado_em=timezone.now()
                    )
                    if not changed:
                        candidatura.refresh_from_db()
                        if candidatura.status != status:
                            raise CandidaturaConflict()
                candidatura = self.get_queryset().get(pk=candidatura.pk)
                data = self.get_serializer(candidatura).data
        except OperationalError:
            raise CandidaturaUnavailable() from None
        return Response(data)

    @action(detail=True, methods=['post'])
    def aprovar(self, request, pk=None):
        return self.decidir(Candidatura.Status.APROVADA)

    @action(detail=True, methods=['post'])
    def recusar(self, request, pk=None):
        return self.decidir(Candidatura.Status.RECUSADA)
