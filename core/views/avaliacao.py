from django.db.models import Avg, Count
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from core.avaliacoes import candidatura_do_participante, confirmar_conclusao, criar_avaliacao, validar_vinculos
from core.models import Avaliacao, ConclusaoTrabalho, User
from core.permissions import account_type
from core.serializers.avaliacao import (
    AvaliacaoCreateSerializer,
    AvaliacaoPublicaSerializer,
    AvaliacaoSerializer,
    ConclusaoSerializer,
    ConfirmacaoConclusaoSerializer,
    ReputacaoSerializer,
)


class AvaliacaoPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and account_type(request.user) in {'empresa', 'usuario'}
        )


class ConclusaoTrabalhoView(APIView):
    permission_classes = [IsAuthenticated, AvaliacaoPermission]
    http_method_names = ['get', 'post', 'head', 'options']

    @extend_schema(responses={200: ConclusaoSerializer, 401: None, 403: None, 404: None, 409: None})
    def get(self, request, candidatura_id):
        candidatura = candidatura_do_participante(request.user, candidatura_id)
        conclusao = ConclusaoTrabalho.objects.filter(candidatura=candidatura).first()
        if conclusao is not None:
            validar_vinculos(conclusao, candidatura)
        data = {
            'candidatura_id': candidatura.pk,
            'empresa_confirmou_em': conclusao.empresa_confirmou_em if conclusao else None,
            'freelancer_confirmou_em': conclusao.freelancer_confirmou_em if conclusao else None,
            'concluido': bool(conclusao and conclusao.concluido and candidatura.status == 'aprovada'),
        }
        return Response(ConclusaoSerializer(data).data)

    @extend_schema(
        summary='Confirmar a conclusão do serviço pela parte autenticada',
        description='Exige candidatura aprovada. Só a confirmação independente das duas partes libera avaliações.',
        request=ConfirmacaoConclusaoSerializer,
        responses={200: ConclusaoSerializer, 400: None, 401: None, 403: None, 404: None, 409: None, 503: None},
    )
    def post(self, request, candidatura_id):
        serializer = ConfirmacaoConclusaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conclusao = confirmar_conclusao(request.user, candidatura_id)
        return Response(ConclusaoSerializer(conclusao).data)


class AvaliacaoViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated, AvaliacaoPermission]
    http_method_names = ['get', 'post', 'head', 'options']
    serializer_class = AvaliacaoSerializer

    def get_queryset(self):
        return Avaliacao.objects.validas()

    @extend_schema(
        summary='Avaliar a outra parte de um trabalho concluído por ambas',
        request=AvaliacaoCreateSerializer,
        responses={201: AvaliacaoSerializer, 400: None, 401: None, 403: None, 404: None, 409: None, 503: None},
    )
    def create(self, request):
        serializer = AvaliacaoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        avaliacao = criar_avaliacao(request.user, **serializer.validated_data)
        return Response(AvaliacaoSerializer(avaliacao).data, status=201)

    def listar(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @extend_schema(responses={200: AvaliacaoSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def minhas(self, request):
        return self.listar(self.get_queryset().filter(avaliador=request.user), AvaliacaoSerializer)

    @extend_schema(responses={200: AvaliacaoSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def recebidas(self, request):
        return self.listar(self.get_queryset().filter(avaliado=request.user), AvaliacaoSerializer)

    def usuario_divulgavel(self, usuario_id):
        # Bound the integer before querying a BigAutoField on either database.
        if len(usuario_id) > len(str(2**63 - 1)) or not 0 < int(usuario_id) <= 2**63 - 1:
            raise NotFound()
        usuario = User.objects.filter(pk=usuario_id, is_active=True, is_staff=False, is_superuser=False).first()
        if usuario is None:
            raise NotFound()
        role = account_type(usuario)
        if role == 'empresa' or (role == 'usuario' and usuario.perfil_publico):
            return usuario
        raise NotFound()

    @extend_schema(
        parameters=[OpenApiParameter('usuario_id', int, OpenApiParameter.PATH)],
        responses={200: AvaliacaoPublicaSerializer(many=True), 401: None, 403: None, 404: None},
    )
    @action(detail=False, methods=['get'], url_path=r'usuarios/(?P<usuario_id>[0-9]+)')
    def publicas(self, request, usuario_id=None):
        usuario = self.usuario_divulgavel(usuario_id)
        return self.listar(self.get_queryset().filter(avaliado=usuario), AvaliacaoPublicaSerializer)

    @extend_schema(
        parameters=[OpenApiParameter('usuario_id', int, OpenApiParameter.PATH)],
        responses={200: ReputacaoSerializer, 401: None, 403: None, 404: None},
    )
    @action(detail=False, methods=['get'], url_path=r'usuarios/(?P<usuario_id>[0-9]+)/reputacao')
    def reputacao(self, request, usuario_id=None):
        usuario = self.usuario_divulgavel(usuario_id)
        values = self.get_queryset().filter(avaliado=usuario).aggregate(media=Avg('nota'), total_avaliacoes=Count('id'))
        if values['media'] is not None:
            values['media'] = round(values['media'], 2)
        return Response(ReputacaoSerializer({'usuario_id': usuario.pk, **values}).data)
