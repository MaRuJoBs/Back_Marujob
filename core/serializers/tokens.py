"""Reject refresh credentials issued before the current password state."""

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class PasswordBoundTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs['refresh'])
        # Use the same identity, activity and password-state checks as access JWTs.
        try:
            JWTAuthentication().get_user(token)
        except (ValueError, TypeError, OverflowError, get_user_model().DoesNotExist):
            raise InvalidToken('Credenciais inválidas.') from None
        # Preserve SimpleJWT's response, expiry and optional rotation semantics.
        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist:
            raise AuthenticationFailed('Credenciais inválidas.') from None
