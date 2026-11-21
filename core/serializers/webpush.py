from urllib.parse import urlsplit

from django.db import IntegrityError
from rest_framework import serializers

from core.models import WebPushSubscription


class WebPushSubscriptionSerializer(serializers.ModelSerializer):
    keys = serializers.DictField(write_only=True)

    class Meta:
        model = WebPushSubscription
        fields = ['id', 'endpoint', 'keys', 'criado_em']
        read_only_fields = ['id', 'criado_em']

    def validate_endpoint(self, value):
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise serializers.ValidationError('O endpoint deve ser uma URL HTTPS válida.')
        return value

    def validate_keys(self, value):
        p256dh = value.get('p256dh')
        auth = value.get('auth')
        if not isinstance(p256dh, str) or not 1 <= len(p256dh) <= 128:
            raise serializers.ValidationError('Chave p256dh inválida.')
        if not isinstance(auth, str) or not 1 <= len(auth) <= 64:
            raise serializers.ValidationError('Chave auth inválida.')
        return {'p256dh': p256dh, 'auth': auth}

    def create(self, validated_data):
        endpoint = validated_data['endpoint']
        keys = validated_data.pop('keys')
        usuario = self.context['request'].user
        current = WebPushSubscription.objects.filter(endpoint=endpoint).first()
        if current is not None:
            if current.usuario_id != usuario.pk:
                raise serializers.ValidationError({'endpoint': ['Esta inscrição já pertence a outra conta.']})
            current.p256dh = keys['p256dh']
            current.auth = keys['auth']
            current.save(update_fields=['p256dh', 'auth', 'atualizado_em'])
            return current
        try:
            return WebPushSubscription.objects.create(endpoint=endpoint, usuario=usuario, **keys)
        except IntegrityError:
            raise serializers.ValidationError({'endpoint': ['Não foi possível registrar esta inscrição.']}) from None

    def to_representation(self, instance):
        return {'id': instance.pk, 'endpoint': instance.endpoint, 'criado_em': instance.criado_em}
