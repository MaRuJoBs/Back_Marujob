"""Small production budgets for authentication; edge rate limits are still required."""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class SensitiveEndpointThrottle(SimpleRateThrottle):
    scope = 'sensitive_auth'

    def get_rate(self):
        return settings.AUTH_THROTTLE_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': request.META.get('REMOTE_ADDR', '')}

    def allow_request(self, request, view):
        if settings.MODE != 'PRODUCTION':
            return True
        return super().allow_request(request, view)


class PasswordEndpointThrottle(SensitiveEndpointThrottle):
    scope = 'sensitive_password'

    def get_rate(self):
        return settings.PASSWORD_THROTTLE_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
