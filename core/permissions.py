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
