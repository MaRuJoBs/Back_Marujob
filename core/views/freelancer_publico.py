"""Company-only directory of freelancers with explicit publication consent."""

import re

from django.db.models import F, Prefetch, Value
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.freelancer_filters import HabilidadeIExact
from core.models import Portfolio, User
from core.permissions import account_type
from core.serializers.freelancer_publico import (
    FreelancerPublicoDetailSerializer,
    FreelancerPublicoListSerializer,
    FreelancerPublicoQuerySerializer,
)


class EmpresaDiretorioPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and account_type(request.user) == 'empresa'
        )


@extend_schema_view(
    list=extend_schema(
        summary='Diretório de freelancers publicados',
        description=(
            'Exige JWT e tipo Empresa inequívoco. Somente freelancers ativos, não administrativos '
            'e com perfil_publico=true. Busca parcial por nome/profissão; cidade e habilidade '
            'por igualdade sem distinguir caixa. Filtros cumulativos antes da paginação por ID.'
        ),
        parameters=[FreelancerPublicoQuerySerializer],
        responses={200: FreelancerPublicoListSerializer(many=True), 400: None, 401: None, 403: None},
    ),
    retrieve=extend_schema(
        summary='Perfil público de freelancer',
        description=(
            'Exige JWT e Empresa. Perfil privado ou inelegível retorna 404. '
            'Inclui apenas projetos com publico=true, ordenados por ID. '
            'Revogar perfil_publico oculta imediatamente perfil e projetos do diretório.'
        ),
        responses={200: FreelancerPublicoDetailSerializer, 401: None, 403: None, 404: None},
    ),
)
class FreelancerPublicoViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, EmpresaDiretorioPermission]
    pagination_class = PageNumberPagination
    serializer_class = FreelancerPublicoListSerializer
    http_method_names = ['get', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FreelancerPublicoDetailSerializer
        return self.serializer_class

    def get_queryset(self):
        queryset = User.objects.filter(
            perfil_publico=True, is_active=True, is_staff=False, is_superuser=False,
            groups__name='Usuário',
        ).exclude(groups__name='Empresa').order_by('id')
        if self.action == 'retrieve':
            return queryset.prefetch_related(Prefetch(
                'portfolios', queryset=Portfolio.objects.filter(publico=True).order_by('id'),
                to_attr='portfolio_publicado',
            ))
        query = FreelancerPublicoQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        for param, field in (
            ('search', 'name__iregex'), ('profissao', 'profissao__iregex'),
            ('cidade', 'cidade_publica__iregex'),
        ):
            if values.get(param):
                pattern = re.escape(values[param])
                if param == 'cidade':
                    pattern = r'\A' + pattern + r'\Z'
                queryset = queryset.filter(**{field: pattern})
        if values.get('habilidade'):
            queryset = queryset.filter(HabilidadeIExact(F('habilidades'), Value(values['habilidade'])))
        return queryset
