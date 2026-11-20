"""Autenticação do WebSocket: o JWT de acesso vem na query string (`?token=<access>`).

A validação é a mesma do DRF (JWTAuthentication): assinatura, expiração, usuário ativo e, como o
projeto usa CHECK_REVOKE_TOKEN, a revogação do token após troca de senha.

Evite logar URLs de WebSocket, já que o token vai nelas.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger('chat')


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope['user'] = await self.get_user(scope)

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, scope):
        token = self._get_token(scope)

        if not token:
            logger.warning('WS recusado: conexão sem token.')

            return AnonymousUser()

        authentication = JWTAuthentication()

        try:
            validated = authentication.get_validated_token(token)

            return authentication.get_user(validated)
        except (InvalidToken, TokenError, AuthenticationFailed):
            logger.warning('WS recusado: credencial inválida, expirada ou revogada.')

            return AnonymousUser()

    @staticmethod
    def _get_token(scope):
        try:
            query_string = scope.get('query_string', b'').decode()
            token = parse_qs(query_string, max_num_fields=16).get('token')
        except (UnicodeDecodeError, ValueError):
            return None

        return token[0] if token else None


def JWTAuthMiddlewareStack(inner):  # noqa: N802 - mesmo estilo de channels.auth.AuthMiddlewareStack
    return JWTAuthMiddleware(inner)
