from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView, get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated

from core.models import EmpresaPerfil, User
from core.permissions import account_type
from core.serializers.empresa_perfil import EmpresaLocalizacaoPublicaSerializer, EmpresaPerfilSerializer


class CompanyProfilePermission(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and request.user.is_active and account_type(request.user) == 'empresa'
        )


class EmpresaPerfilView(RetrieveUpdateAPIView):
    serializer_class = EmpresaPerfilSerializer
    permission_classes = [IsAuthenticated, CompanyProfilePermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        profile = EmpresaPerfil.objects.select_related('empresa').filter(empresa=self.request.user).first()
        # GET has no write side effect; PATCH creates the optional row atomically.
        return profile if profile is not None else EmpresaPerfil(empresa=self.request.user)


@extend_schema(
    summary='Consultar somente cidade e UF divulgáveis de uma empresa',
    description='Sem GPS, bairro, endereço ou contatos. Localização declarada, sem verificação geográfica.',
    responses={200: EmpresaLocalizacaoPublicaSerializer, 404: None},
)
class EmpresaLocalizacaoPublicaView(RetrieveAPIView):
    serializer_class = EmpresaLocalizacaoPublicaSerializer
    permission_classes = [AllowAny]
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        # Select only the two public columns, never personal or precise location data.
        return (
            User.objects
            .filter(
                is_active=True,
                is_staff=False,
                is_superuser=False,
                groups__name='Empresa',
            )
            .exclude(groups__name='Usuário')
            .values('empresa_perfil__cidade', 'empresa_perfil__uf')
        )

    def get_object(self):
        empresa_id = self.kwargs['empresa_id']
        if not 0 < empresa_id < 2**63:
            raise NotFound()
        row = get_object_or_404(self.get_queryset(), pk=empresa_id)
        return {'cidade': row['empresa_perfil__cidade'] or '', 'uf': row['empresa_perfil__uf'] or ''}
