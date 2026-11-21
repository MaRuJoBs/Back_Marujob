import base64
import json
import logging
import re
from http import HTTPStatus

import requests
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.utils import timezone
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from core.models import NotificacaoFreelancer, PushSubscription

logger = logging.getLogger(__name__)

MAX_DEVICES = 5
# Fixed HTTPS origins and opaque provider paths. No userinfo, ports, query, or redirects.
PUSH_ENDPOINT = re.compile(
    r'https://(?:fcm\.googleapis\.com/(?:fcm/send|wp)/|'
    r'updates\.push\.services\.mozilla\.com/(?:wpush/v[12]|push/v1)/|'
    r'web\.push\.apple\.com/)[A-Za-z0-9_.~:=+_-]+',
    re.ASCII,
)
EXPIRED_STATUSES = {404, 410}
PUSH_TEXT = {
    NotificacaoFreelancer.Evento.APROVADA: 'Sua candidatura foi aprovada.',
    NotificacaoFreelancer.Evento.RECUSADA: 'Sua candidatura não foi selecionada.',
}


def endpoint_permitido(endpoint):
    if not PUSH_ENDPOINT.fullmatch(endpoint):
        return False
    # Dot segments could change the effective provider path.
    token = endpoint.rsplit('/', 1)[-1]
    return token not in {'.', '..'}


def vapid_configurado():
    subject = settings.VAPID_SUBJECT
    private_key = settings.VAPID_PRIVATE_KEY
    if not subject.startswith('mailto:') or not re.fullmatch(r'[A-Za-z0-9_-]{43}', private_key):
        return None
    try:
        validate_email(subject.removeprefix('mailto:'))
        vapid = Vapid.from_string(private_key)
    except (ValueError, ValidationError):
        return None
    public_key = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    if base64.urlsafe_b64encode(public_key).decode().rstrip('=') != settings.VAPID_PUBLIC_KEY:
        return None
    return vapid


class PushSession(requests.Session):
    def post(self, url, **kwargs):
        response = super().post(url, **kwargs, allow_redirects=False)
        if not HTTPStatus.OK <= response.status_code <= HTTPStatus.ACCEPTED:
            raise WebPushException('Push Service recusou a entrega.', response=response)
        return response

    def get_redirect_target(self, response):
        return None


def enviar_push(notificacao):
    vapid = vapid_configurado()
    if vapid is None:
        return
    dispositivos = PushSubscription.objects.filter(usuario_id=notificacao.destinatario_id, usuario__is_active=True)
    agora = timezone.now()
    dispositivos.filter(expira_em__lte=agora).delete()
    ativos = dispositivos.filter(Q(expira_em__isnull=True) | Q(expira_em__gt=agora))
    subscriptions = list(ativos.order_by('pk')[:MAX_DEVICES])
    if not subscriptions:
        return

    payload = json.dumps({
        'event': notificacao.evento,
        'notification_id': notificacao.pk,
        'title': notificacao.titulo,
        'body': PUSH_TEXT[notificacao.evento],
        'url': '/notificacoes',
    })
    with PushSession() as session:
        session.trust_env = False
        for subscription in subscriptions:
            # A fresh check also prevents invalidating a subscription refreshed during delivery.
            atual = ativos.filter(pk=subscription.pk, atualizado_em=subscription.atualizado_em)
            if endpoint_permitido(subscription.endpoint) and atual.exists():
                status = enviar_dispositivo(session, vapid, subscription, payload)
                if status in EXPIRED_STATUSES:
                    atual.delete()


def enviar_dispositivo(session, vapid, subscription, payload):
    response = None
    try:
        response = webpush(
            subscription_info={
                'endpoint': subscription.endpoint,
                'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
            },
            data=payload,
            vapid_private_key=vapid,
            vapid_claims={'sub': settings.VAPID_SUBJECT},
            requests_session=session,
            timeout=2,
            ttl=300,
        )
        return response.status_code
    except WebPushException as exc:
        response = exc.response
        status = response.status_code if response is not None else None
        logger.warning('Push Service recusou uma entrega. HTTP %s.', status)
        return status
    except Exception:
        # Transport and signing errors can contain subscription credentials.
        logger.warning('Falha na tentativa de Web Push.')
        return None
    finally:
        if response is not None:
            response.close()
