from rest_framework.permissions import SAFE_METHODS, BasePermission


def account_type(user):
    groups = set(user.groups.filter(name__in=['Usuário', 'Empresa']).values_list('name', flat=True))
    if groups == {'Empresa'}:
        return 'empresa'
    if groups == {'Usuário'}:
        return 'usuario'
    return None


class CompanyOpportunityPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (request.method in SAFE_METHODS or account_type(request.user) == 'empresa')
        )

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or obj.empresa_id == request.user.pk


class FreelancerPortfolioPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (request.method in SAFE_METHODS or account_type(request.user) == 'usuario')
        )

    def has_object_permission(self, request, view, obj):
        return obj.usuario_id == request.user.pk


class CandidaturaPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = account_type(request.user)
        view.account_role = role
        if view.action in {'aprovar', 'recusar'}:
            return role == 'empresa'
        if request.method == 'POST':
            return role == 'usuario'
        return role in {'usuario', 'empresa'}

    def has_object_permission(self, request, view, obj):
        if view.action in {'aprovar', 'recusar'}:
            return view.account_role == 'empresa' and obj.oportunidade.empresa_id == request.user.pk
        if request.method not in SAFE_METHODS:
            return False
        role = account_type(request.user)
        if role == 'usuario':
            return obj.freelancer_id == request.user.pk
        return role == 'empresa' and obj.oportunidade.empresa_id == request.user.pk


class NotificacaoEmpresaPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and account_type(request.user) == 'empresa')

    def has_object_permission(self, request, view, obj):
        return obj.empresa_id == request.user.pk and obj.candidatura.oportunidade.empresa_id == request.user.pk
