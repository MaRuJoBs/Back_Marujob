"""B45: contracts deliberately limited until publication is authorized."""

from rest_framework import serializers

from core.models import User


class FreelancerPublicoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id']
        read_only_fields = fields


class FreelancerPublicoDetailSerializer(FreelancerPublicoListSerializer):
    portfolio = serializers.SerializerMethodField()

    class Meta(FreelancerPublicoListSerializer.Meta):
        fields = ['id', 'portfolio']
        read_only_fields = fields

    def get_portfolio(self, obj) -> list:
        # B40 portfolios are private; no publication authorization exists.
        return []


class FreelancerPublicoQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    profissao = serializers.CharField(required=False, allow_blank=True, max_length=255)
    habilidade = serializers.CharField(required=False, allow_blank=True, max_length=100)
    cidade = serializers.CharField(required=False, allow_blank=True, max_length=255)
    page = serializers.IntegerField(required=False, min_value=1, max_value=1000000)

    def to_internal_value(self, data):
        errors = {}
        for key in data:
            if key not in self.fields:
                errors[key] = 'Parâmetro não suportado.'
            elif hasattr(data, 'getlist') and len(data.getlist(key)) != 1:
                errors[key] = 'Informe o parâmetro uma única vez.'
            elif key == 'page' and not str(data[key]).strip():
                errors[key] = 'Informe uma página válida.'
        if errors:
            raise serializers.ValidationError(errors)
        normalized = data.copy()
        for key in ('search', 'profissao', 'habilidade', 'cidade'):
            if key in normalized and isinstance(normalized[key], str):
                normalized[key] = ' '.join(normalized[key].split())
        return super().to_internal_value(normalized)

    def validate(self, attrs):
        errors = {
            key: 'Filtro indisponível até a definição e implementação da divulgação autorizada.'
            for key in ('search', 'profissao', 'habilidade', 'cidade')
            if attrs.get(key)
        }
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
