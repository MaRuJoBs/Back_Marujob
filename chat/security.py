"""Validação da origem (cabeçalho Origin) das conexões WebSocket do chat.

O front roda em outro domínio, então AllowedHostsOriginValidator (que compara com ALLOWED_HOSTS do
backend) recusaria o próprio front. As origens aceitas são as mesmas do CORS da API:
CORS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGIN_REGEXES e CORS_ALLOW_ALL_ORIGINS (django-cors-headers).

As configurações são lidas a cada conexão, para refletirem override_settings nos testes.
"""

import re

from channels.security.websocket import OriginValidator
from django.conf import settings


class CorsOriginValidator(OriginValidator):
    def __init__(self, application):
        # Lista vazia: sem '*', uma conexão sem Origin é sempre recusada pelo OriginValidator.
        super().__init__(application, [])

    def validate_origin(self, parsed_origin):
        if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
            return True

        if any(
            self.match_allowed_origin(parsed_origin, origin) for origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', ())
        ):
            return True

        origin = f'{parsed_origin.scheme}://{parsed_origin.netloc}'

        return any(re.match(pattern, origin) for pattern in getattr(settings, 'CORS_ALLOWED_ORIGIN_REGEXES', ()))
