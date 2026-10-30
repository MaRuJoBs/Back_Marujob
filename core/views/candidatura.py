from django.db import IntegrityError, OperationalError, transaction
from rest_framework import mixins
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.viewsets import GenericViewSet

from core.models import Candidatura
from core.permissions import CandidaturaPermission, account_type
from core.serializers.candidatura import CandidaturaCreateSerializer, CandidaturaFilterSerializer, CandidaturaSerializer


class CandidaturaUnavailable(APIException):
    status_code = 503
    default_detail = 'Serviço de candidaturas temporariamente indisponível. Tente novamente.'
    default_code = 'candidatura_unavailable'


class CandidaturaViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    permission_classes = [CandidaturaPermission]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        return CandidaturaCreateSerializer if self.action == 'create' else CandidaturaSerializer

    def get_queryset(self):
        queryset = Candidatura.objects.select_related('freelancer', 'oportunidade')
        role = account_type(self.request.user)
        if role == 'usuario':
            queryset = queryset.filter(freelancer=self.request.user)
        elif role == 'empresa':
            queryset = queryset.filter(oportunidade__empresa=self.request.user)
        else:
            return queryset.none()
        filters = CandidaturaFilterSerializer(data=self.request.query_params.dict())
        filters.is_valid(raise_exception=True)
        return queryset.filter(**filters.validated_data)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(freelancer=self.request.user, status=Candidatura.Status.PENDENTE)
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
