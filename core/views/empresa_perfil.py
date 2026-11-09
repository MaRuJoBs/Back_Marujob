from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated

from core.models import EmpresaPerfil
from core.permissions import account_type
from core.serializers.empresa_perfil import EmpresaPerfilSerializer


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
