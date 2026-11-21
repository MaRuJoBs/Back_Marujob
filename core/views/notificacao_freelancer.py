from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import mixins, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.models import NotificacaoFreelancer
from core.permissions import FreelancerNotificationPermission
from core.serializers.notificacao_freelancer import (
    NotificacaoFreelancerFilterSerializer,
    NotificacaoFreelancerSerializer,
)


@extend_schema_view(list=extend_schema(parameters=[NotificacaoFreelancerFilterSerializer]))
@method_decorator(never_cache, name='dispatch')
class NotificacaoFreelancerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    permission_classes = [FreelancerNotificationPermission]
    serializer_class = NotificacaoFreelancerSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return NotificacaoFreelancer.objects.none()
        queryset = NotificacaoFreelancer.objects.filter(destinatario=self.request.user)
        if self.action == 'list':
            filtros = NotificacaoFreelancerFilterSerializer(data=self.request.query_params.dict())
            filtros.is_valid(raise_exception=True)
            queryset = queryset.filter(**filtros.validated_data)
        return queryset.select_related('candidatura')

    @extend_schema(request=None)
    @action(detail=True, methods=['patch'], url_path='marcar-lida')
    def marcar_lida(self, request, pk=None):
        notificacao = self.get_object()
        if not notificacao.lida:
            self.get_queryset().filter(pk=notificacao.pk).update(lida=True)
            notificacao.lida = True
        return Response(self.get_serializer(notificacao).data)

    @extend_schema(
        request=None,
        responses=inline_serializer(
            name='NotificacoesFreelancerAtualizadas',
            fields={
                'atualizadas': serializers.IntegerField(),
            },
        ),
    )
    @action(detail=False, methods=['post'], url_path='marcar-todas-lidas')
    def marcar_todas_lidas(self, request):
        total = self.get_queryset().filter(lida=False).update(lida=True)
        return Response({'atualizadas': total})
