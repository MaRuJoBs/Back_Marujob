"""B45 restricted directory. No existing profile has publication authorization."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.models import User
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
        summary='Diretório de freelancers (entrega parcial)',
        description=(
            'Exige JWT e tipo Empresa inequívoco. Retorna lista vazia enquanto não houver '
            'autorização de publicação de perfis. Filtros não vazios retornam 400; '
            'não há campos profissionais públicos aprovados.'
        ),
        parameters=[FreelancerPublicoQuerySerializer],
        responses={200: FreelancerPublicoListSerializer(many=True), 400: None, 401: None, 403: None},
    ),
    retrieve=extend_schema(
        summary='Perfil autorizado de freelancer (entrega parcial)',
        description=(
            'Exige JWT e Empresa. Atualmente retorna 404 para todo ID: '
            'não existe autorização de publicação. Portfólios permanecem privados.'
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
        # Never infer consent from group membership or perfil_configurado.
        # Replace this gate only when an approved publication mechanism exists.
        return User.objects.none().order_by('id')

    def list(self, request, *args, **kwargs):
        query = FreelancerPublicoQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return super().list(request, *args, **kwargs)
