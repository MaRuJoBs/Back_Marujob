from django.conf import settings
from django.db import models


class WebPushSubscription(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webpush_subscriptions')
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=64)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
