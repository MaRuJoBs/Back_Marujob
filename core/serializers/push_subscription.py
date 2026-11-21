import base64
import re
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric import ec
from django.utils import timezone
from rest_framework import serializers

from core.push_delivery import endpoint_permitido

UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MAX_EXPIRATION_MS = 253402300799000


class PushEndpointSerializer(serializers.Serializer):
    endpoint = serializers.CharField(max_length=2048, trim_whitespace=False)

    def validate_endpoint(self, value):
        if not endpoint_permitido(value):
            raise serializers.ValidationError('Endpoint HTTPS de um Push Service compatível é obrigatório.')
        return value


def decode_key(value, expected_size):
    if re.fullmatch(r'[A-Za-z0-9_+/-]+={0,2}', value):
        padded = value.rstrip('=')
        raw = base64.b64decode(padded + '=' * (-len(padded) % 4), altchars=b'-_', validate=True)
        if len(raw) == expected_size:
            return raw
    raise ValueError('Invalid subscription key')


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=88, trim_whitespace=False)
    auth = serializers.CharField(max_length=24, trim_whitespace=False)

    def validate_p256dh(self, value):
        try:
            raw = decode_key(value, 65)
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        except ValueError:
            raise serializers.ValidationError('Chave pública P-256 inválida.') from None
        return base64.urlsafe_b64encode(raw).decode().rstrip('=')

    def validate_auth(self, value):
        try:
            raw = decode_key(value, 16)
        except ValueError:
            raise serializers.ValidationError('Segredo de autenticação inválido.') from None
        return base64.urlsafe_b64encode(raw).decode().rstrip('=')


class PushSubscriptionSerializer(PushEndpointSerializer):
    keys = PushKeysSerializer()
    expirationTime = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=MAX_EXPIRATION_MS)

    def validate_expirationTime(self, value):
        if value is None:
            return None
        expires = UNIX_EPOCH + timedelta(milliseconds=value)
        if expires <= timezone.now():
            raise serializers.ValidationError('A subscription expirou.')
        return expires


class VapidPublicKeySerializer(serializers.Serializer):
    publicKey = serializers.CharField()
