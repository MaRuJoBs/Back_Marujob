from django.db import OperationalError
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.models import Notificacao
from core.permissions import NotificacaoEmpresaPermission
from core.serializers.notificacao import NotificacaoFilterSerializer, NotificacaoSerializer


class NotificacaoUnavailable(APIException):
    status_code = 503
    default_detail = 'Serviço de notificações temporariamente indisponível. Tente novamente.'
    default_code = 'notificacao_unavailable'


class NotificacaoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    permission_classes = [NotificacaoEmpresaPermission]
    serializer_class = NotificacaoSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = Notificacao.objects.filter(
            empresa=self.request.user,
            candidatura__oportunidade__empresa=self.request.user,
        ).select_related('candidatura__freelancer', 'candidatura__oportunidade')
        if self.action != 'list':
            return queryset
        filters = NotificacaoFilterSerializer(data=self.request.query_params.dict())
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        if 'lida' in values:
            queryset = queryset.filter(lida=values['lida'])
        if 'status' in values:
            queryset = queryset.filter(candidatura__status=values['status'])
        return queryset

    @action(detail=True, methods=['patch'], url_path='marcar-lida')
    def marcar_lida(self, request, pk=None):
        try:
            notification = self.get_object()
            # Only this boolean is writable, regardless of the submitted payload.
            self.get_queryset().filter(pk=notification.pk, lida=False).update(lida=True)
            notification.lida = True
        except OperationalError:
            raise NotificacaoUnavailable() from None
        return Response(self.get_serializer(notification).data)
