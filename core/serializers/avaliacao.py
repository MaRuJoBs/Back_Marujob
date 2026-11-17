from rest_framework import serializers

from core.models import Avaliacao


class StrictPayloadSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            extra = set(data) - set(self.fields)
            if extra:
                raise serializers.ValidationError({key: ['Campo não permitido.'] for key in sorted(extra)})
        return super().to_internal_value(data)


class InteiroSerializerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, (bool, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


class AvaliacaoCreateSerializer(StrictPayloadSerializer):
    candidatura_id = InteiroSerializerField(min_value=1, max_value=2**63 - 1)
    nota = InteiroSerializerField(min_value=1, max_value=5)
    comentario = serializers.CharField(required=False, allow_blank=True, max_length=1000, default='')


class ConfirmacaoConclusaoSerializer(StrictPayloadSerializer):
    """An empty payload: neither identity nor timestamp is client-controlled."""


class ConclusaoSerializer(serializers.Serializer):
    candidatura_id = serializers.IntegerField(read_only=True)
    empresa_confirmou_em = serializers.DateTimeField(read_only=True, allow_null=True)
    freelancer_confirmou_em = serializers.DateTimeField(read_only=True, allow_null=True)
    concluido = serializers.BooleanField(read_only=True)


class AvaliacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Avaliacao
        fields = ['id', 'candidatura', 'avaliador', 'avaliado', 'nota', 'comentario', 'criado_em', 'atualizado_em']
        read_only_fields = fields


class AvaliacaoPublicaSerializer(serializers.ModelSerializer):
    """Public comments never reveal the author or their private working relationship."""

    class Meta:
        model = Avaliacao
        fields = ['id', 'nota', 'comentario', 'criado_em']
        read_only_fields = fields


class ReputacaoSerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField(read_only=True)
    media = serializers.FloatField(read_only=True, allow_null=True)
    total_avaliacoes = serializers.IntegerField(read_only=True)
