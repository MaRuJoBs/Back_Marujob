from rest_framework import serializers
from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from core.models import Freelance
from core.permissions import CompanyOpportunityPermission
from core.serializers import FreelanceSerializer


class OpportunitySearchFilter(SearchFilter):
    def get_search_terms(self, request):
        value = request.query_params.get(self.search_param, '')
        if len(value) > 200:
            raise serializers.ValidationError({'search': ['A pesquisa deve ter no máximo 200 caracteres.']})
        terms = super().get_search_terms(request)
        if len(terms) > 20:
            raise serializers.ValidationError({'search': ['A pesquisa deve ter no máximo 20 termos.']})
        return terms


class OpportunityQuerySerializer(serializers.Serializer):
    tag = serializers.CharField(required=False, allow_blank=True, max_length=50)
    preco_min = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=0)
    preco_max = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=0)

    def validate(self, attrs):
        if 'preco_min' in attrs and 'preco_max' in attrs and attrs['preco_min'] > attrs['preco_max']:
            raise serializers.ValidationError({'preco_max': 'Deve ser maior ou igual a preco_min.'})
        return attrs


class FreelanceViewSet(ModelViewSet):
    permission_classes = [CompanyOpportunityPermission]
    queryset = Freelance.objects.all().order_by('id')
    serializer_class = FreelanceSerializer
    filter_backends = [OpportunitySearchFilter]
    search_fields = ['titulo']

    def filter_queryset(self, queryset):
        # Query parameters restrict the collection only; detail/CRUD stay unchanged.
        if self.action != 'list':
            return queryset
        params = OpportunityQuerySerializer(data=dict(self.request.query_params.items()))
        params.is_valid(raise_exception=True)
        values = params.validated_data
        if values.get('tag'):
            queryset = queryset.filter(tag__iexact=values['tag'])
        if 'preco_min' in values:
            queryset = queryset.filter(preco__gte=values['preco_min'])
        if 'preco_max' in values:
            queryset = queryset.filter(preco__lte=values['preco_max'])
        return super().filter_queryset(queryset)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user)
