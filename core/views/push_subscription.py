from django.conf import settings
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.models import PushSubscription, User
from core.permissions import FreelancerNotificationPermission
from core.push_delivery import MAX_DEVICES, vapid_configurado
from core.serializers.push_subscription import (
    PushEndpointSerializer,
    PushSubscriptionSerializer,
    VapidPublicKeySerializer,
)


class PushUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Web Push temporariamente indisponível.'


class VapidKeyThrottle(AnonRateThrottle):
    scope = 'vapid_public_key'
    rate = '60/min'

    def get_ident(self, request):
        return request.META.get('REMOTE_ADDR', '')


class PushSubscriptionThrottle(UserRateThrottle):
    scope = 'push_subscription'
    rate = '20/min'


class VapidPublicKeyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [VapidKeyThrottle]

    @extend_schema(responses=VapidPublicKeySerializer)
    def get(self, request):
        if vapid_configurado() is None:
            raise PushUnavailable()
        return Response({'publicKey': settings.VAPID_PUBLIC_KEY})


@method_decorator(never_cache, name='dispatch')
class PushSubscriptionView(APIView):
    permission_classes = [FreelancerNotificationPermission]
    throttle_classes = [PushSubscriptionThrottle]

    @extend_schema(request=PushSubscriptionSerializer, responses={204: None})
    def post(self, request):
        if vapid_configurado() is None:
            raise PushUnavailable()
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        keys = dados['keys']
        defaults = {'usuario_id': request.user.pk, 'expira_em': dados.get('expirationTime'), **keys}

        try:
            with transaction.atomic():
                User.objects.select_for_update().only('pk').get(pk=request.user.pk)
                subscriptions = PushSubscription.objects.filter(usuario=request.user)
                subscriptions.filter(expira_em__lte=timezone.now()).delete()
                subscription, created = PushSubscription.objects.select_for_update().get_or_create(
                    endpoint=dados['endpoint'], defaults=defaults
                )
                if subscription.usuario_id != request.user.pk and not (
                    constant_time_compare(subscription.auth, keys['auth'])
                    and constant_time_compare(subscription.p256dh, keys['p256dh'])
                ):
                    raise ValidationError({'endpoint': 'Não foi possível registrar esta subscription.'})
                novas = created or subscription.usuario_id != request.user.pk
                if novas and subscriptions.exclude(pk=subscription.pk).count() >= MAX_DEVICES:
                    raise ValidationError({'endpoint': f'Limite de {MAX_DEVICES} dispositivos por conta.'})
                if not created:
                    for field, value in defaults.items():
                        setattr(subscription, field, value)
                    subscription.save(update_fields=[*defaults, 'atualizado_em'])
        except OperationalError:
            raise PushUnavailable() from None
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=PushEndpointSerializer, responses={204: None})
    def delete(self, request):
        serializer = PushEndpointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            PushSubscription.objects.filter(
                usuario=request.user, endpoint=serializer.validated_data['endpoint']
            ).delete()
        except OperationalError:
            raise PushUnavailable() from None
        return Response(status=status.HTTP_204_NO_CONTENT)
