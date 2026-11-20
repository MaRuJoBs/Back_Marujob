"""Regressions for the B54 release review; synthetic accounts and disposable DB only."""

# ruff: noqa: PT009, PT027
import socket
from contextlib import ExitStack
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from core.models import User
from core.tests import test_authentication

THROTTLE_BUDGET = 2


class ReleaseConfigurationTests(SimpleTestCase):
    def config(self, **overrides):
        return test_authentication.ProductionSettingsTests().load_settings(**overrides)

    def test_production_redirects_http_and_sets_hsts_on_https(self):
        config = self.config()
        with override_settings(
            SECURE_SSL_REDIRECT=config.get('SECURE_SSL_REDIRECT', False),
            SECURE_HSTS_SECONDS=config.get('SECURE_HSTS_SECONDS', 0),
            SECURE_PROXY_SSL_HEADER=config['SECURE_PROXY_SSL_HEADER'],
        ):
            middleware = SecurityMiddleware(lambda request: HttpResponse())
            self.assertEqual(middleware(RequestFactory().get('/api/usuarios/me/')).status_code, 301)
            response = middleware(RequestFactory().get('/', secure=True))
            self.assertIn('Strict-Transport-Security', response)

    def test_production_requires_explicit_database_and_nontrivial_secret(self):
        for overrides in [{'DATABASE_URL': None}, {'DATABASE_URL': ''}, {'SECRET_KEY': 'x' * 64}]:
            with self.subTest(overrides=list(overrides)), self.assertRaises(ImproperlyConfigured):
                self.config(**overrides)

    def test_production_rejects_insecure_or_malformed_origins(self):
        for key in ['CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS']:
            for origin in [
                'http://web.example.invalid',
                'https://web.example.invalid/path',
                'https://user:password@web.example.invalid',
                '*',
            ]:
                with self.subTest(key=key, origin=origin), self.assertRaises(ImproperlyConfigured):
                    self.config(**{key: origin})

    def test_development_still_accepts_local_http_and_database_default(self):
        config = self.config(MODE='DEVELOPMENT', DATABASE_URL=None)
        self.assertFalse(config.get('SECURE_SSL_REDIRECT', False))
        self.assertEqual(config.get('SECURE_HSTS_SECONDS', 0), 0)
        self.assertEqual(config['DATABASES']['default']['ENGINE'], 'django.db.backends.sqlite3')

    def test_audit_socketpair_works_but_direct_connections_remain_blocked(self):
        with ExitStack() as context:
            # Also safe under ordinary manage.py test, without the audit runner.
            if socket.socket.connect.__name__ != 'deny_connection':
                from scripts import audit_b54  # noqa: PLC0415

                context.enter_context(patch.object(socket.socket, 'connect', audit_b54.deny_connection))
                context.enter_context(patch.object(socket.socket, 'connect_ex', audit_b54.deny_connection))
                context.enter_context(patch.object(socket, 'socketpair', audit_b54.local_socketpair))
            first, second = socket.socketpair()
            try:
                first.sendall(b'audit')
                self.assertEqual(second.recv(5), b'audit')
            finally:
                first.close()
                second.close()
            with socket.socket() as connection:
                with self.assertRaisesRegex(OSError, 'B54 audit forbids'):
                    connection.connect(('192.0.2.1', 443))
                with self.assertRaisesRegex(OSError, 'B54 audit forbids'):
                    connection.connect_ex(('192.0.2.1', 443))

    def test_invalid_authentication_limits_fail_at_configuration_time(self):
        for key in ['AUTH_THROTTLE_RATE', 'PASSWORD_THROTTLE_RATE']:
            for rate in ['0/min', '-1/min', '20/invalid', 'bad']:
                with self.subTest(key=key, rate=rate), self.assertRaises(ImproperlyConfigured):
                    self.config(**{key: rate})

    def test_production_can_share_authentication_budgets_over_redis(self):
        config = self.config(REDIS_URL='redis://cache.example.invalid:6379/0')
        self.assertEqual(config['CACHES']['default']['BACKEND'], 'django.core.cache.backends.redis.RedisCache')


@override_settings(MODE='PRODUCTION', AUTH_THROTTLE_RATE='2/min', PASSWORD_THROTTLE_RATE='2/min')
class SensitiveEndpointLimitTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_failed_logins_are_limited_and_forwarded_header_cannot_reset_budget(self):
        for attempt in range(3):
            response = self.client.post(
                '/api/token/',
                {
                    'email': 'absent@b54.example.invalid',
                    'password': 'Synthetic-B54-73829!',
                },
                HTTP_X_FORWARDED_FOR=f'192.0.2.{attempt + 1}',
            )
            self.assertEqual(response.status_code, 429 if attempt == THROTTLE_BUDGET else 401)
        self.assertIn('Retry-After', response)

    def test_all_public_authentication_routes_share_the_ip_budget(self):
        self.assertEqual(self.client.post('/api/token/', {}).status_code, 400)
        self.assertEqual(self.client.post('/api/token/refresh/', {}).status_code, 400)
        for path in ['/api/token/verify/', '/api/auth/google/', '/api/registro/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {}).status_code, 429)
        # Another direct peer has its own budget.
        self.assertEqual(self.client.post('/api/token/', {}, REMOTE_ADDR='192.0.2.50').status_code, 400)

    def test_password_operations_share_a_user_budget_even_if_ip_changes(self):
        user = User.objects.create_user('password@b54.example.invalid', 'Synthetic-B54-73829!')
        self.client.force_authenticate(user)
        for attempt, path in enumerate([
            '/api/auth/trocar-senha/',
            '/api/auth/definir-senha/',
            '/api/auth/trocar-senha/',
        ]):
            response = self.client.post(path, {}, REMOTE_ADDR=f'192.0.2.{attempt + 1}')
            self.assertEqual(response.status_code, 429 if attempt == THROTTLE_BUDGET else 400)

    @override_settings(MODE='DEVELOPMENT')
    def test_local_development_authentication_is_not_throttled(self):
        for _ in range(3):
            self.assertEqual(self.client.post('/api/token/', {}).status_code, 400)

    def test_throttled_google_request_never_calls_upstream(self):
        with patch('core.views.user.id_token.verify_oauth2_token', side_effect=ValueError('synthetic')) as verify:
            for _ in range(3):
                response = self.client.post('/api/auth/google/', {'credential': 'synthetic'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(verify.call_count, 2)
