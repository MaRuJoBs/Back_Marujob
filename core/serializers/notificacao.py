from rest_framework import serializers

from core.models import Candidatura, Notificacao
from core.serializers.candidatura import CandidatoProfissionalSerializer


class NotificacaoSerializer(serializers.ModelSerializer):
    freelancer = serializers.IntegerField(source='candidatura.freelancer_id', read_only=True)
    freelancer_detalhes = CandidatoProfissionalSerializer(source='candidatura.freelancer', read_only=True)
    oportunidade = serializers.IntegerField(source='candidatura.oportunidade_id', read_only=True)
    oportunidade_titulo = serializers.CharField(source='candidatura.oportunidade.titulo', read_only=True)
    status = serializers.CharField(source='candidatura.status', read_only=True)
    candidatura_criado_em = serializers.DateTimeField(source='candidatura.criado_em', read_only=True)

    class Meta:
        model = Notificacao
        fields = [
            'id',
            'candidatura',
            'freelancer',
            'freelancer_detalhes',
            'oportunidade',
            'oportunidade_titulo',
            'status',
            'candidatura_criado_em',
            'criado_em',
            'lida',
        ]
        read_only_fields = fields


class NotificacaoFilterSerializer(serializers.Serializer):
    lida = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(choices=Candidatura.Status.choices, required=False)
