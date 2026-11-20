"""
ASGI do projeto: HTTP pelo Django e WebSocket pelo chat (Django Channels).

O WebSocket só aceita as origens liberadas no CORS (chat.security.CorsOriginValidator) e autentica
pelo JWT de acesso na query string (chat.middleware.JWTAuthMiddleware).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# Inicializa o Django antes de importar qualquer coisa que use modelos.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from chat.middleware import JWTAuthMiddlewareStack  # noqa: E402
from chat.routing import websocket_urlpatterns  # noqa: E402
from chat.security import CorsOriginValidator  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': CorsOriginValidator(JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))),
})
