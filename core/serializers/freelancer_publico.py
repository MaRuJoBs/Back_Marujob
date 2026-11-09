"""Explicit public projections, independent of private profile serializers."""

from rest_framework import serializers

from core.models import Portfolio, User
from core.serializers.fields import ValidatedImageField


class PortfolioPublicoSerializer(serializers.ModelSerializer):
    imagem = ValidatedImageField(read_only=True)

    class Meta:
        model = Portfolio
        fields = ['id', 'titulo', 'categoria', 'descricao', 'tags', 'link', 'imagem']
        read_only_fields = fields


class FreelancerPublicoListSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='name', read_only=True, allow_null=True)
    cidade = serializers.CharField(source='cidade_publica', read_only=True)
    foto_perfil = ValidatedImageField(source='profile_image', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'nome', 'profissao', 'cidade', 'habilidades', 'foto_perfil']
        read_only_fields = fields


class FreelancerPublicoDetailSerializer(FreelancerPublicoListSerializer):
    descricao = serializers.CharField(source='sobre', read_only=True)
    portfolio = PortfolioPublicoSerializer(source='portfolio_publicado', many=True, read_only=True)

    class Meta(FreelancerPublicoListSerializer.Meta):
        fields = [*FreelancerPublicoListSerializer.Meta.fields, 'descricao', 'portfolio']
        read_only_fields = fields


class FreelancerPublicoQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    profissao = serializers.CharField(required=False, allow_blank=True, max_length=255)
    habilidade = serializers.CharField(required=False, allow_blank=True, max_length=100)
    cidade = serializers.CharField(required=False, allow_blank=True, max_length=120)
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
