import json
import logging

from django.conf import settings

from core.models import WebPushSubscription

logger = logging.getLogger(__name__)


def send_web_push(usuario_id, title, body, url):
    """Send a best-effort Web Push notification to every browser registered by the user."""
    private_key = getattr(settings, 'WEBPUSH_VAPID_PRIVATE_KEY', '')
    public_key = getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')
    subject = getattr(settings, 'WEBPUSH_VAPID_SUBJECT', '')
    if not (private_key and public_key and subject):
        return
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.error('Dependência pywebpush não instalada; notificações push desativadas.')
        return

    payload = json.dumps({'title': title, 'body': body, 'url': url})
    try:
        subscriptions = WebPushSubscription.objects.filter(usuario_id=usuario_id)
        for subscription in subscriptions.iterator():
            try:
                webpush(
                    subscription_info={
                        'endpoint': subscription.endpoint,
                        'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={'sub': subject},
                )
            except WebPushException as exc:
                response = getattr(exc, 'response', None)
                if response is not None and response.status_code in {404, 410}:
                    subscription.delete()
                else:
                    logger.warning('Web Push delivery failed for subscription %s.', subscription.pk)
            except Exception:
                logger.exception('Unexpected Web Push failure for subscription %s.', subscription.pk)
    except Exception:
        logger.exception('Unable to load Web Push subscriptions for user %s.', usuario_id)
