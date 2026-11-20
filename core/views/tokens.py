"""Existing SimpleJWT endpoints with a shared authentication request budget."""

from rest_framework_simplejwt import views

from core.throttles import SensitiveEndpointThrottle


class TokenObtainPairView(views.TokenObtainPairView):
    throttle_classes = [SensitiveEndpointThrottle]


class TokenRefreshView(views.TokenRefreshView):
    throttle_classes = [SensitiveEndpointThrottle]


class TokenVerifyView(views.TokenVerifyView):
    throttle_classes = [SensitiveEndpointThrottle]
