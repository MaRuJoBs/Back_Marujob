from rest_framework import serializers

from core.models import Candidatura, Freelance, User
from core.serializers.freelance import FreelanceSerializer


class CandidatoProfissionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'profissao', 'habilidades', 'profile_image']
        read_only_fields = fields


class CandidaturaCreateSerializer(serializers.ModelSerializer):
    oportunidade = serializers.PrimaryKeyRelatedField(
        queryset=Freelance.objects.all(),
        pk_field=serializers.IntegerField(min_value=1, max_value=2**63 - 1),
    )

    class Meta:
        model = Candidatura
        fields = ['id', 'freelancer', 'oportunidade', 'status', 'criado_em', 'atualizado_em']
        read_only_fields = ['id', 'freelancer', 'status', 'criado_em', 'atualizado_em']
        # The database constraint arbitrates duplicates, including concurrent requests.
        validators = []


class CandidaturaSerializer(serializers.ModelSerializer):
    oportunidade_detalhes = FreelanceSerializer(source='oportunidade', read_only=True)
    freelancer_detalhes = CandidatoProfissionalSerializer(source='freelancer', read_only=True)

    class Meta:
        model = Candidatura
        fields = [
            'id',
            'freelancer',
            'oportunidade',
            'status',
            'criado_em',
            'atualizado_em',
            'oportunidade_detalhes',
            'freelancer_detalhes',
        ]
        read_only_fields = fields


class CandidaturaFilterSerializer(serializers.Serializer):
    oportunidade = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)
