"""Run read-only Django checks/tests with synthetic settings and no outbound sockets.

Usage: pdm run python scripts/audit_b54.py test --noinput
       pdm run python scripts/audit_b54.py --production check --deploy
Never runs application migrations or reads the shared .env/database.
"""

import os
import socket
import sys
import threading
from pathlib import Path

_socketpair_context = threading.local()
_connect = socket.socket.connect
_socketpair = socket.socketpair


def deny_connection(connection, address):
    # Windows implements socketpair() through a private loopback connection.
    # Only the synchronous stdlib socketpair call in this thread may connect.
    if getattr(_socketpair_context, 'active', False):
        return _connect(connection, address)
    raise OSError('B54 audit forbids outbound network connections')


def local_socketpair(*args, **kwargs):
    previous = getattr(_socketpair_context, 'active', False)
    _socketpair_context.active = True
    try:
        return _socketpair(*args, **kwargs)
    finally:
        _socketpair_context.active = previous


def main():
    arguments = sys.argv[1:]
    production = '--production' in arguments
    if production:
        arguments.remove('--production')
    if not arguments or arguments[0] not in {'test', 'check', 'makemigrations', 'showmigrations'}:
        raise SystemExit('Allowed: test, check, makemigrations --check --dry-run, showmigrations --plan')
    if arguments[0] == 'makemigrations' and not {'--check', '--dry-run'} <= set(arguments):
        raise SystemExit('makemigrations requires --check --dry-run')
    if any(argument.startswith('--settings') for argument in arguments):
        raise SystemExit('Settings are fixed by this isolated audit runner')
    if production and arguments[0] != 'check':
        raise SystemExit('--production permits check only')
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.update({
        'PYTHON_DOTENV_DISABLED': '1',
        'MODE': 'PRODUCTION' if production else 'DEVELOPMENT',
        'DEBUG': 'False',
        'SECRET_KEY': 'B54-synthetic-key-for-offline-audit-only-83927-abcd-51973-efgh',
        'DATABASE_URL': 'sqlite:///:memory:',
        'ALLOWED_HOSTS': 'audit.example.invalid',
        'CORS_ALLOWED_ORIGINS': 'https://web.example.invalid',
        'CSRF_TRUSTED_ORIGINS': 'https://audit.example.invalid',
        'GOOGLE_CLIENT_ID': 'b54-offline-client',
        'CLOUDINARY_URL': 'cloudinary://audit-key:audit-secret@audit-cloud',
        'TRUST_X_FORWARDED_PROTO': 'False',
        'REDIS_URL': '',
        'AUTH_THROTTLE_RATE': '20/min',
        'PASSWORD_THROTTLE_RATE': '5/min',
        'MAX_IMAGE_UPLOAD_BYTES': '5242880',
        'DJANGO_SETTINGS_MODULE': 'app.settings' if production else 'core.tests.settings',
    })
    # Twisted's Windows waker creates its own loopback sockets at import time.
    # Initialize only the ASGI runtime before guarding application execution.
    import daphne.server  # noqa: F401,PLC0415

    socket.socket.connect = deny_connection
    socket.socket.connect_ex = deny_connection
    socket.socketpair = local_socketpair
    from django.core.management import execute_from_command_line  # noqa: PLC0415

    execute_from_command_line(['manage.py', *arguments])


if __name__ == '__main__':
    main()
