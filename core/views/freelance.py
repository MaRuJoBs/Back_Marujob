from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from core.models import Freelance
from core.permissions import CompanyOpportunityPermission
from core.serializers import FreelanceSerializer


class OpportunitySearchFilter(SearchFilter):
    max_search_length = 200
    max_search_terms = 20

    def get_search_terms(self, request):
        value = request.query_params.get(self.search_param, '')
        if len(value) > self.max_search_length:
            raise serializers.ValidationError({'search': ['A pesquisa deve ter no máximo 200 caracteres.']})
        terms = super().get_search_terms(request)
        if len(terms) > self.max_search_terms:
            raise serializers.ValidationError({'search': ['A pesquisa deve ter no máximo 20 termos.']})
        return terms


class OpportunityQuerySerializer(serializers.Serializer):
    tag = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
        help_text='Texto completo da tag, sem distinção de caixa conforme o banco. Vazio não restringe.',
    )
    preco_min = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text='Limite inferior inclusivo de preco; não filtra a faixa salarial.',
    )
    preco_max = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text='Limite superior inclusivo de preco; deve ser maior ou igual a preco_min.',
    )
    tipo_contratacao = serializers.ChoiceField(
        choices=Freelance.TipoContratacao.choices,
        required=False,
        allow_blank=True,
        help_text='Valor exato do tipo de contratação. Vazio não restringe.',
    )
    nivel_experiencia = serializers.ChoiceField(
        choices=Freelance.NivelExperiencia.choices,
        required=False,
        allow_blank=True,
        help_text='Valor exato do nível de experiência, incluindo acentos. Vazio não restringe.',
    )

    def validate(self, attrs):
        if 'preco_min' in attrs and 'preco_max' in attrs and attrs['preco_min'] > attrs['preco_max']:
            raise serializers.ValidationError({'preco_max': 'Deve ser maior ou igual a preco_min.'})
        return attrs


@extend_schema_view(list=extend_schema(parameters=[OpportunityQuerySerializer]))
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
        for field in ('tipo_contratacao', 'nivel_experiencia'):
            if values.get(field):
                queryset = queryset.filter(**{field: values[field]})
        if 'preco_min' in values:
            queryset = queryset.filter(preco__gte=values['preco_min'])
        if 'preco_max' in values:
            queryset = queryset.filter(preco__lte=values['preco_max'])
        return super().filter_queryset(queryset)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user)
