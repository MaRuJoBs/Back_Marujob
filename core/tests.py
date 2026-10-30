import os
import runpy
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Django APITestCase assertions retain detailed response diagnostics.
# ruff: noqa: PT009, PT027
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from google.auth import crypt, jwt
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from core.models import Freelance, Portfolio, User


@override_settings(GOOGLE_CLIENT_ID='test-client')
class AuthenticationTests(APITestCase):
    password = 'Secure!Marujo-39482'

    @classmethod
    def setUpTestData(cls):
        cls.worker = User.objects.create_user('worker@example.com', cls.password)
        cls.company = User.objects.create_user('company@example.com', cls.password)
        cls.other = User.objects.create_user('other@example.com', cls.password)
        cls.worker.groups.add(Group.objects.get(name='Usuário'))
        group = Group.objects.get(name='Empresa')
        cls.company.groups.add(group)
        cls.other.groups.add(group)

    def login_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def test_registration(self):
        for tipo, group in [('usuario', 'Usuário'), ('empresa', 'Empresa')]:
            with self.subTest(tipo=tipo):
                data = {'email': f'{tipo}@example.com', 'password': self.password, 'tipo': tipo}
                response = self.client.post('/api/registro/', data, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                self.assertNotIn('password', response.data)
                user = User.objects.get(email=data['email'])
                self.assertTrue(user.check_password(self.password))
                self.assertTrue(user.groups.filter(name=group).exists())
                data['email'] = data['email'].upper()
                self.assertEqual(self.client.post('/api/registro/', data).status_code, 400)
        self.assertEqual(self.client.post('/api/registro/', {}).status_code, 400)
        self.assertEqual(
            self.client.post(
                '/api/registro/',
                {
                    'email': 'weak@example.com',
                    'password': '12345678',
                    'tipo': 'usuario',
                },
            ).status_code,
            400,
        )

    def test_jwt(self):
        response = self.client.post('/api/token/', {'email': self.worker.email, 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.post('/api/token/', {'email': self.worker.email, 'password': 'wrong'}).status_code, 401
        )
        for key in ['access', 'refresh']:
            self.assertEqual(self.client.post('/api/token/verify/', {'token': response.data[key]}).status_code, 200)
        self.assertEqual(
            self.client.post('/api/token/refresh/', {'refresh': response.data['refresh']}).status_code, 200
        )
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': response.data['access']}).status_code, 401)
        expired = AccessToken.for_user(self.worker)
        expired.set_exp(lifetime=timedelta(seconds=-1))
        for token in ['invalid', str(expired), response.data['refresh']]:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
        for token in ['invalid', str(expired)]:
            self.assertEqual(self.client.post('/api/token/verify/', {'token': token}).status_code, 401)
        expired_refresh = RefreshToken.for_user(self.worker)
        expired_refresh.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(expired_refresh)}).status_code, 401)

    def test_company_login_and_inactive_account(self):
        credentials = {'email': self.company.email, 'password': self.password}
        self.assertEqual(self.client.post('/api/token/', credentials).status_code, 200)
        self.company.is_active = False
        self.company.save()
        self.assertEqual(self.client.post('/api/token/', credentials).status_code, 401)

    def test_profile_and_private_endpoints(self):
        for url in ['/api/usuarios/me/', '/api/usuarios/', '/api/freelances/', '/api/portfolios/']:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.login_as(self.worker)
        response = self.client.patch(
            '/api/usuarios/me/',
            {
                'name': 'Updated',
                'id': self.company.pk,
                'groups': [self.company.groups.first().pk],
                'tipo': 'empresa',
                'is_staff': True,
                'is_superuser': True,
                'password': 'hacked',
                'google_id': 'hacked',
                'user_permissions': [1],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tipo'], 'usuario')
        self.assertEqual(response.data['groups'][0]['name'], 'Usuário')
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_staff)
        self.assertFalse(self.worker.is_superuser)
        self.assertTrue(self.worker.check_password(self.password))
        self.assertIsNone(self.worker.google_id)
        self.assertEqual(self.client.get(f'/api/usuarios/{self.company.pk}/').status_code, 404)
        self.login_as(self.company)
        self.assertEqual(self.client.get('/api/usuarios/me/').data['tipo'], 'empresa')
        self.assertEqual(self.client.put('/api/usuarios/me/', {'tipo': 'usuario'}).status_code, 405)
        self.assertEqual(self.client.put(f'/api/usuarios/{self.worker.pk}/', {}).status_code, 405)

    def test_ambiguous_groups_fail_closed(self):
        for groups in [[], list(Group.objects.filter(name__in=['Empresa', 'Usuário']))]:
            self.worker.groups.set(groups)
            self.login_as(self.worker)
            self.assertIsNone(self.client.get('/api/usuarios/me/').data['tipo'])
            self.assertEqual(self.client.post('/api/freelances/', {}).status_code, 403)
            self.assertEqual(self.client.post('/api/portfolios/', {}).status_code, 403)

    def test_opportunities(self):
        data = {'titulo': 'Job', 'preco': '100.00', 'tempo': '1 dia', 'empresa': self.other.pk}
        self.login_as(self.worker)
        self.assertEqual(self.client.get('/api/freelances/').status_code, 200)
        self.assertEqual(self.client.post('/api/freelances/', data).status_code, 403)
        self.login_as(self.company)
        response = self.client.post('/api/freelances/', data)
        self.assertEqual(response.status_code, 201, response.data)
        job = Freelance.objects.get(pk=response.data['id'])
        self.assertEqual(job.empresa, self.company)
        url = f'/api/freelances/{job.pk}/'
        self.assertEqual(self.client.patch(url, {'empresa': self.other.pk, 'titulo': 'Changed'}).status_code, 200)
        self.assertEqual(self.client.put(url, data).status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.empresa, self.company)
        for actor in [self.other, self.worker]:
            self.login_as(actor)
            self.assertEqual(self.client.patch(url, {'titulo': 'Forbidden'}).status_code, 403)
            self.assertEqual(self.client.put(url, data).status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 403)
        self.login_as(self.company)
        orphan = Freelance.objects.create(titulo='Legacy', preco=1, tempo='1')
        self.assertEqual(self.client.delete(f'/api/freelances/{orphan.pk}/').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_administrative_groups_preserved(self):
        admin_group = Group.objects.create(name='Administradores')
        self.company.groups.add(admin_group)
        self.login_as(self.company)
        self.assertEqual(self.client.patch('/api/usuarios/me/', {'groups': []}, format='json').status_code, 200)
        self.assertTrue(self.company.groups.filter(pk=admin_group.pk).exists())
        self.assertEqual(self.client.get('/api/usuarios/me/').data['tipo'], 'empresa')

    def test_portfolios(self):
        self.login_as(self.worker)
        response = self.client.post(
            '/api/portfolios/',
            {
                'titulo': 'Portfolio',
                'categoria': 'Dev',
                'descricao': 'Work',
                'usuario': self.company.pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        portfolio = Portfolio.objects.get(pk=response.data['id'])
        self.assertEqual(portfolio.usuario, self.worker)
        url = f'/api/portfolios/{portfolio.pk}/'
        self.assertEqual(self.client.patch(url, {'usuario': self.other.pk, 'titulo': 'New'}).status_code, 200)
        portfolio.refresh_from_db()
        self.assertEqual(portfolio.usuario, self.worker)
        self.other.groups.set(self.worker.groups.all())
        self.login_as(self.other)
        self.assertEqual(self.client.patch(url, {'titulo': 'Forbidden'}).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.login_as(self.company)
        self.assertEqual(self.client.post('/api/portfolios/', {}).status_code, 403)
        self.assertEqual(self.client.patch(url, {}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.login_as(self.worker)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_passwords(self):
        self.assertEqual(self.client.post('/api/auth/definir-senha/', {'senha': self.password}).status_code, 401)
        self.login_as(self.worker)
        self.assertEqual(self.client.post('/api/auth/definir-senha/', {'senha': self.password}).status_code, 400)
        url = '/api/auth/trocar-senha/'
        self.assertEqual(self.client.post(url, {'senha_atual': 'wrong', 'nova_senha': self.password}).status_code, 400)
        self.assertEqual(
            self.client.post(url, {'senha_atual': self.password, 'nova_senha': '12345678'}).status_code, 400
        )
        self.assertEqual(
            self.client.post(url, {'senha_atual': self.password, 'nova_senha': 'New!Secure-Marujob391'}).status_code,
            200,
        )
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password('New!Secure-Marujob391'))
        self.worker.set_unusable_password()
        self.worker.google_id = 'google-sub'
        self.worker.save()
        self.assertEqual(self.client.post('/api/auth/definir-senha/', {'senha': '12345678'}).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/definir-senha/', {'senha': self.password}).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/definir-senha/', {'senha': self.password}).status_code, 400)

    @patch('core.views.user.requests.get')
    @patch('core.views.user.id_token.verify_oauth2_token')
    def test_google(self, verify, download):
        url = '/api/auth/google/'
        verify.side_effect = ValueError('private provider details')
        response = self.client.post(url, {'credential': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('private provider', str(response.data))
        verify.side_effect = None
        for tipo, group in [('usuario', 'Usuário'), ('empresa', 'Empresa')]:
            verify.return_value = {
                'email': f'google-{tipo}@example.com',
                'email_verified': True,
                'sub': f'sub-{tipo}',
                'aud': 'test-client',
            }
            response = self.client.post(url, {'credential': 'valid', 'tipo': tipo, 'cadastro': True}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(verify.call_args.args[2], 'test-client')
            self.assertEqual(response.data['user']['tipo'], tipo)
            self.assertEqual(response.data['user']['groups'][0]['name'], group)
            self.assertTrue(response.data['precisa_definir_senha'])
            self.assertEqual(self.client.post(url, {'credential': 'valid', 'cadastro': 'false'}).status_code, 200)
            self.assertEqual(
                self.client.post(
                    url, {'credential': 'valid', 'tipo': tipo, 'cadastro': True}, format='json'
                ).status_code,
                400,
            )
        verify.return_value = {
            'email': self.worker.email,
            'email_verified': True,
            'sub': 'other-sub',
            'aud': 'test-client',
        }
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 400)
        self.worker.google_id = 'expected-sub'
        self.worker.save()
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 400)
        verify.return_value['sub'] = 'expected-sub'
        self.worker.is_active = False
        self.worker.save()
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 401)
        verify.return_value['email'] = 'missing@example.com'
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 404)
        verify.return_value['email_verified'] = False
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 400)
        verify.return_value['email_verified'] = True
        verify.return_value['aud'] = 'wrong-client'
        self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 400)
        with override_settings(GOOGLE_CLIENT_ID=None):
            self.assertEqual(self.client.post(url, {'credential': 'valid'}).status_code, 503)
        download.assert_not_called()

    @patch('google.oauth2.id_token._fetch_certs')
    def test_google_server_verification_offline(self, fetch_certs):
        # Real signature, issuer, audience and expiry validation; only key retrieval is mocked.
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        signer = crypt.RSASigner.from_string(private_pem, key_id='test-key')
        fetch_certs.return_value = {'test-key': public_pem}
        now = int(time.time())
        claims = {
            'iss': 'https://accounts.google.com',
            'aud': 'test-client',
            'sub': 'offline-sub',
            'iat': now - 10,
            'exp': now + 300,
            'email': 'offline@example.com',
            'email_verified': True,
        }
        for invalid_claims in [
            {'iss': 'https://attacker.example.com'},
            {'aud': 'wrong-client'},
            {'exp': now - 1},
            {'email_verified': False},
            {'sub': ''},
        ]:
            with self.subTest(invalid_claims=invalid_claims):
                token = jwt.encode(signer, claims | invalid_claims).decode()
                response = self.client.post(
                    '/api/auth/google/',
                    {
                        'credential': token,
                        'cadastro': True,
                        'tipo': 'usuario',
                    },
                    format='json',
                )
                self.assertEqual(response.status_code, 400, response.data)
        token = jwt.encode(signer, claims).decode()
        self.assertEqual(
            self.client.post(
                '/api/auth/google/',
                {
                    'credential': token,
                    'cadastro': True,
                    'tipo': 'usuario',
                },
                format='json',
            ).status_code,
            200,
        )
        signature = token.rsplit('.', 1)[1]
        tampered = token.rsplit('.', 1)[0] + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:]
        self.assertEqual(self.client.post('/api/auth/google/', {'credential': tampered}).status_code, 400)


class ProductionSettingsTests(SimpleTestCase):
    def load_settings(self, **overrides):
        environment = {
            'MODE': 'PRODUCTION',
            'DEBUG': 'False',
            'SECRET_KEY': 'test-only-key-' * 5,
            'ALLOWED_HOSTS': 'api.example.com',
            'CORS_ALLOWED_ORIGINS': 'https://example.com',
            'DATABASE_URL': 'sqlite:///:memory:',
        }
        environment.update(overrides)
        with patch.dict(os.environ, environment), patch('dotenv.load_dotenv'):
            return runpy.run_path(str(Path(__file__).resolve().parent.parent / 'app' / 'settings.py'))

    def test_production_explicit_configuration(self):
        with patch('builtins.print') as output:
            settings = self.load_settings()
        self.assertFalse(settings['CORS_ALLOW_ALL_ORIGINS'])
        self.assertEqual(settings['CORS_ALLOWED_ORIGINS'], ['https://example.com'])
        self.assertEqual(settings['ALLOWED_HOSTS'], ['api.example.com'])
        self.assertEqual(settings['SIMPLE_JWT']['ACCESS_TOKEN_LIFETIME'], timedelta(minutes=180))
        self.assertEqual(settings['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'], timedelta(days=1))
        output.assert_not_called()

    def test_production_rejects_insecure_configuration(self):
        for overrides in [
            {'DEBUG': 'True'},
            {'SECRET_KEY': 'django-insecure'},
            {'ALLOWED_HOSTS': '*'},
            {'ALLOWED_HOSTS': ''},
        ]:
            with self.subTest(overrides=overrides), self.assertRaises(ImproperlyConfigured):
                self.load_settings(**overrides)
