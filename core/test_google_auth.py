import json
import os
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import Group
from google.auth import crypt, jwt
from google.auth.exceptions import TransportError
from rest_framework.test import APITestCase

from core.models import User


CLIENT_ID = '123-test-client.apps.googleusercontent.com'


class GoogleAuthenticationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='google@example.com', google_id='google-subject', name='Google Test'
        )
        group, _ = Group.objects.get_or_create(name='Usuário')
        cls.user.groups.add(group)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        cls.signer = crypt.RSASigner.from_string(private_pem, key_id='test-key')
        cls.certificate_response = SimpleNamespace(
            status=200, data=json.dumps({'test-key': public_pem}).encode()
        )

    def setUp(self):
        environment = patch.dict(os.environ, {'GOOGLE_CLIENT_ID': CLIENT_ID})
        environment.start()
        self.addCleanup(environment.stop)
        self.transport = Mock(return_value=self.certificate_response)
        request = patch('core.views.user.google_requests.Request', return_value=self.transport)
        request.start()
        self.addCleanup(request.stop)

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            'iss': 'https://accounts.google.com',
            'aud': CLIENT_ID,
            'iat': now - 1,
            'exp': now + 3600,
            'sub': 'google-subject',
            'email': 'google@example.com',
            'email_verified': True,
            'name': 'Google Test',
        }
        claims.update(overrides)
        return jwt.encode(self.signer, claims).decode()

    def exchange(self, token, **data):
        return self.client.post(
            '/api/auth/google/', {'credential': token, 'cadastro': False, **data}, format='json'
        )

    def test_small_clock_difference_succeeds_and_me_includes_groups(self):
        response = self.exchange(self.token(iat=int(time.time()) + 3))
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        profile = self.client.get('/api/usuarios/me/')
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data['groups'], ['Usuário'])
        self.assertTrue(profile.data['precisa_definir_senha'])

    def test_large_future_issue_time_is_rejected(self):
        response = self.exchange(self.token(iat=int(time.time()) + 60))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('access', response.data)

    def test_expired_token_is_rejected(self):
        response = self.exchange(self.token(iat=int(time.time()) - 3600, exp=int(time.time()) - 60))
        self.assertEqual(response.status_code, 400)

    def test_wrong_audience_is_rejected(self):
        response = self.exchange(self.token(aud='other-client.apps.googleusercontent.com'))
        self.assertEqual(response.status_code, 400)

    def test_invalid_signature_is_rejected(self):
        parts = self.token().split('.')
        signature = parts[2]
        parts[2] = ('A' if signature[0] != 'A' else 'B') + signature[1:]
        self.assertEqual(self.exchange('.'.join(parts)).status_code, 400)

    def test_missing_client_id_does_not_disable_audience_validation(self):
        with patch.dict(os.environ, {'GOOGLE_CLIENT_ID': ''}):
            response = self.exchange(self.token())
        self.assertEqual(response.status_code, 503)
        self.transport.assert_not_called()

    def test_certificate_connection_failure_returns_retryable_error(self):
        self.transport.side_effect = TransportError('Certificate connection failed')
        self.assertEqual(self.exchange(self.token()).status_code, 503)

    def test_inactive_account_cannot_receive_jwt(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        response = self.exchange(self.token())
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('access', response.data)

    def test_company_google_registration_has_company_group(self):
        token = self.token(email='company@example.com', sub='company-subject')
        response = self.exchange(token, cadastro=True, tipo='empresa')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        profile = self.client.get('/api/usuarios/me/')
        self.assertEqual(profile.data['groups'], ['Empresa'])

    def test_profile_does_not_allow_changing_groups(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            '/api/usuarios/me/', {'groups': ['Empresa']}, format='multipart'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(list(self.user.groups.values_list('name', flat=True)), ['Usuário'])
