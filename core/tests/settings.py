"""Configuração exclusiva dos testes: nunca utiliza o banco da aplicação."""

import os

os.environ['MODE'] = 'DEVELOPMENT'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'feat38-test-secret-key-only-for-isolated-tests'

from app.settings import *  # noqa: E402,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {'NAME': ':memory:'},
    },
}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
