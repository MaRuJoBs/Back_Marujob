import re
import unicodedata

from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import ChoiceField, DateField, ModelSerializer, ValidationError

from core.models import Freelance


class PublicationDateField(DateField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', data):
            self.fail('invalid', format='YYYY-MM-DD')
        return super().to_internal_value(data)


@extend_schema_field({'type': 'string', 'enum': Freelance.Status.values}, component_name='OpportunityStatus')
class OpportunityStatusField(ChoiceField):
    """Keep opportunity and application status enums distinct in OpenAPI."""


class FreelanceSerializer(ModelSerializer):
    status = OpportunityStatusField(choices=Freelance.Status.choices, required=False)
    data_publicacao = PublicationDateField(
        required=False,
        allow_null=True,
        format='%Y-%m-%d',
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = Freelance
        fields = '__all__'
        read_only_fields = ['empresa']
        extra_kwargs = {
            'requisitos': {'trim_whitespace': False},
            'beneficios': {'trim_whitespace': False},
            'jornada_trabalho': {'trim_whitespace': False},
            'salario_minimo': {'coerce_to_string': True},
            'salario_maximo': {'coerce_to_string': True},
        }

    def validate_preco(self, value):
        if value < 0:
            raise ValidationError('O preço não pode ser negativo.')
        return value

    def validate_cidade(self, value):
        value = unicodedata.normalize('NFC', value)
        if value and (
            not any(character.isalpha() for character in value)
            or any(not character.isalpha() and character not in " .'-’" for character in value)
        ):
            raise ValidationError('Informe uma cidade com letras, espaços, hífens, pontos ou apóstrofos.')
        return value

    def validate(self, attrs):
        minimum = attrs.get('salario_minimo', getattr(self.instance, 'salario_minimo', None))
        maximum = attrs.get('salario_maximo', getattr(self.instance, 'salario_maximo', None))
        if (minimum is None) != (maximum is None):
            missing_field = 'salario_minimo' if minimum is None else 'salario_maximo'
            raise ValidationError({
                missing_field: ['Preencha os dois extremos da faixa salarial ou deixe ambos nulos.']
            })
        if minimum is not None and maximum < minimum:
            raise ValidationError({'salario_maximo': ['O valor máximo deve ser maior ou igual ao mínimo.']})
        return attrs
