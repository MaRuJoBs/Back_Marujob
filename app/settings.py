import os
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define o modo de execução da aplicação
MODE = os.getenv('MODE', '').strip().upper()
if MODE not in {'DEVELOPMENT', 'MIGRATE', 'PRODUCTION'}:
    raise ImproperlyConfigured('MODE deve ser DEVELOPMENT, MIGRATE ou PRODUCTION.')

# Constrói o caminho base do projeto, usado para definir caminhos relativos
BASE_DIR = Path(__file__).resolve().parent.parent

# Segurança e configuração básica
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure')
DEBUG = os.getenv('DEBUG', 'False').strip().lower() == 'true'
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1' if MODE == 'DEVELOPMENT' else '').split(',')
    if h.strip()
]
MIN_SECRET_KEY_LENGTH = 50
MIN_SECRET_KEY_CHARACTERS = 5
UNSAFE_SECRET_KEY = (
    SECRET_KEY.startswith('django-insecure')
    or len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH
    or len(set(SECRET_KEY)) < MIN_SECRET_KEY_CHARACTERS
)
if MODE != 'DEVELOPMENT' and any((DEBUG, UNSAFE_SECRET_KEY, not ALLOWED_HOSTS, '*' in ALLOWED_HOSTS)):
    raise ImproperlyConfigured('Configure SECRET_KEY forte, ALLOWED_HOSTS explícitos e DEBUG=False.')
DEVELOPMENT_FRONTEND_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS', DEVELOPMENT_FRONTEND_ORIGINS if MODE == 'DEVELOPMENT' else ''
    ).split(',')
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        DEVELOPMENT_FRONTEND_ORIGINS + ',http://localhost:3000,http://localhost:8000' if MODE == 'DEVELOPMENT' else '',
    ).split(',')
    if origin.strip()
]
if MODE == 'PRODUCTION':
    for origins in (CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS):
        for origin in origins:
            try:
                parsed = urlsplit(origin)
                valid = (
                    parsed.scheme == 'https'
                    and parsed.hostname
                    and not parsed.username
                    and not parsed.password
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and '*' not in parsed.netloc
                    and parsed.port != 0
                )
            except ValueError:
                valid = False
            if not valid:
                raise ImproperlyConfigured('Origens de CORS e CSRF em produção devem ser origens HTTPS explícitas.')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
# Enable only behind a controlled proxy that strips/replaces client-supplied headers.
TRUST_X_FORWARDED_PROTO = os.getenv('TRUST_X_FORWARDED_PROTO', 'False').strip().lower() == 'true'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if TRUST_X_FORWARDED_PROTO else None
# Admin sessions and CSRF cookies must only travel over HTTPS in production.
SESSION_COOKIE_SECURE = MODE == 'PRODUCTION'
CSRF_COOKIE_SECURE = MODE == 'PRODUCTION'
SECURE_SSL_REDIRECT = MODE == 'PRODUCTION'
# Start with a short HSTS lifetime; do not enroll other subdomains or preload.
SECURE_HSTS_SECONDS = 3600 if MODE == 'PRODUCTION' else 0

# Aplicações instaladas
INSTALLED_APPS = [
    # daphne precisa vir primeiro: substitui o runserver por um servidor ASGI (HTTP + WebSocket).
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'corsheaders',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'channels',
    'core',
    'chat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION = 'app.asgi.application'

# Chat em tempo real (Django Channels). Com REDIS_URL o channel layer é compartilhado entre processos;
# sem ele, fica em memória (serve só para desenvolvimento e testes, com um único processo).
REDIS_URL = os.getenv('REDIS_URL', '').strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

if MODE == 'PRODUCTION' and REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'marujob-auth',
        },
    }

# Tamanho máximo de um anexo do chat, em MB.
try:
    CHAT_MAX_UPLOAD_MB = int(os.getenv('CHAT_MAX_UPLOAD_MB', '10'))
except ValueError:
    raise ImproperlyConfigured('CHAT_MAX_UPLOAD_MB deve ser um inteiro positivo.') from None
if CHAT_MAX_UPLOAD_MB <= 0:
    raise ImproperlyConfigured('CHAT_MAX_UPLOAD_MB deve ser um inteiro positivo.')

# Banco de dados
if MODE != 'DEVELOPMENT' and not os.getenv('DATABASE_URL', '').strip():
    raise ImproperlyConfigured('Configure DATABASE_URL explicitamente fora de desenvolvimento.')
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Configurações de internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Configurações de arquivos estáticos
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configurações de arquivos de mídia
# Configurações de arquivos de mídia
MEDIA_URL = '/media/'
FILE_UPLOAD_PERMISSIONS = 0o640
try:
    MAX_IMAGE_UPLOAD_BYTES = int(os.getenv('MAX_IMAGE_UPLOAD_BYTES', str(5 * 1024 * 1024)))
except ValueError:
    raise ImproperlyConfigured('MAX_IMAGE_UPLOAD_BYTES deve ser um inteiro positivo em bytes.') from None
if MAX_IMAGE_UPLOAD_BYTES <= 0:
    raise ImproperlyConfigured('MAX_IMAGE_UPLOAD_BYTES deve ser um inteiro positivo em bytes.')

# Configurações do Cloudinary


if MODE == 'DEVELOPMENT':
    MY_IP = os.getenv('MY_IP', '127.0.0.1')

    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

elif MODE in {'MIGRATE', 'PRODUCTION'}:
    MEDIA_URL = '/media/'

    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

else:
    raise ValueError(f'MODE inválido: {MODE}')

# Tipo padrão de campo para chaves primárias
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configurações do DRF e drf-spectacular (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': '<PROJETO> API',
    'DESCRIPTION': 'API para o projeto <descreva aqui seu projeto>.',
    'VERSION': '1.0.0',
}

# Modelo de usuário personalizado
AUTH_USER_MODEL = 'core.User'

# Configurações do Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 10,
}

# Applied only in PRODUCTION. The reverse proxy must replace REMOTE_ADDR with
# the real peer address; arbitrary X-Forwarded-For headers are never trusted here.
AUTH_THROTTLE_RATE = os.getenv('AUTH_THROTTLE_RATE', '20/min')
PASSWORD_THROTTLE_RATE = os.getenv('PASSWORD_THROTTLE_RATE', '5/min')
for rate in (AUTH_THROTTLE_RATE, PASSWORD_THROTTLE_RATE):
    if not re.fullmatch(r'[1-9][0-9]*/(?:second|minute|hour|day|sec|min|s|m|h|d)s?', rate):
        raise ImproperlyConfigured('Configure limites de autenticação positivos, por exemplo 20/min.')

# Configurações do Simple JWT
SIMPLE_JWT = {
    'CHECK_REVOKE_TOKEN': True,
    'TOKEN_REFRESH_SERIALIZER': 'core.serializers.tokens.PasswordBoundTokenRefreshSerializer',
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=180),  # Tokens de acesso expiram em 3 horas
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Tokens de atualização expiram em 1 dia
    'AUTH_HEADER_TYPES': ('Bearer',),
}
