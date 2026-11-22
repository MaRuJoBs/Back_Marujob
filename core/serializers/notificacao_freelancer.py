from rest_framework import serializers

from core.models import NotificacaoFreelancer


class NotificacaoFreelancerSerializer(serializers.ModelSerializer):
    oportunidade = serializers.IntegerField(source='candidatura.oportunidade_id', read_only=True, allow_null=True)

    class Meta:
        model = NotificacaoFreelancer
        fields = ['id', 'candidatura', 'oportunidade', 'evento', 'titulo', 'mensagem', 'lida', 'criado_em']
        read_only_fields = fields


class NotificacaoFreelancerFilterSerializer(serializers.Serializer):
    lida = serializers.BooleanField(required=False)
