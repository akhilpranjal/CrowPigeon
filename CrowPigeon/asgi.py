"""ASGI entrypoint — routes HTTP and WebSocket connections.

HTTP requests go through Django's standard ASGI handler.
WebSocket connections pass through session + auth middleware before
reaching the chat consumer.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.sessions import SessionMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CrowPigeon.settings')

django_asgi_app = get_asgi_application()

# Import after Django is set up so that models are available.
from chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        SessionMiddlewareStack(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
