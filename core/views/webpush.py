from django.conf import settings
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from core.models import WebPushSubscription
from core.serializers.webpush import WebPushSubscriptionSerializer


class WebPushPublicKeyView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({'public_key': getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')})


class WebPushSubscriptionViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WebPushSubscriptionSerializer
    http_method_names = ['post', 'delete', 'head', 'options']

    def get_queryset(self):
        return WebPushSubscription.objects.filter(usuario=self.request.user)
