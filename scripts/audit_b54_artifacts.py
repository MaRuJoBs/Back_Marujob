"""Inspect committed artifacts in memory; emit counts only, never record values.

Does not open the working SQLite database, load dotenv, modify Git or write files.
Historical presence is inventoried; historical blob contents are not scanned.
"""

import json
import re
import sqlite3
import subprocess
from collections import Counter
from io import BytesIO
from pathlib import Path

from PIL import Image

GPS_EXIF_TAG = 34853


def git(*arguments):
    return subprocess.run(
        ['git', *arguments],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def summarize_users(users):
    return {
        'rows': len(users),
        'email_populated': sum(bool(user.get('email')) for user in users),
        'hash_algorithms': dict(
            Counter(
                'pbkdf2_sha256' if str(user.get('password', '')).startswith('pbkdf2_sha256$') else 'other_or_unusable'
                for user in users
                if user.get('password')
            )
        ),
        'origin': 'not_verified',
    }


def main():
    paths = git('ls-tree', '-r', '--name-only', 'HEAD').decode().splitlines()
    report = {'head': git('rev-parse', 'HEAD').decode().strip()}
    dump = git('show', 'HEAD:dump.json')
    rows = json.loads(dump)
    report['committed_dump'] = summarize_users([row['fields'] for row in rows if row.get('model') == 'core.user'])
    database = git('show', 'HEAD:db.sqlite3')
    connection = sqlite3.connect(':memory:')
    try:
        connection.deserialize(database)
        connection.execute('PRAGMA query_only=ON')
        users = connection.execute('SELECT email, password FROM core_user').fetchall()
        report['committed_database'] = summarize_users([
            dict(zip(['email', 'password'], row, strict=True)) for row in users
        ])
    finally:
        connection.close()
    media = [path for path in paths if path.startswith('media/')]
    report['media'] = {'tracked_files': len(media), 'exif_files': 0, 'gps_exif_files': 0, 'unreadable': 0}
    for path in media:
        try:
            with Image.open(BytesIO(git('show', 'HEAD:' + path))) as image:
                exif = image.getexif()
                report['media']['exif_files'] += bool(exif)
                report['media']['gps_exif_files'] += GPS_EXIF_TAG in exif
        except (OSError, ValueError):
            report['media']['unreadable'] += 1
    report['history_touching_artifacts'] = {
        path: len(git('log', '--all', '--format=%H', '--', path).splitlines())
        for path in ['db.sqlite3', 'dump.json', 'media', '.env', '.env.exemplo']
    }
    # Heuristics are indicators, not credential validity tests or a complete scan.
    patterns = {
        'jwt_like': rb'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
        'private_key_marker': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'github_token_like': rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    }
    template = git('show', 'HEAD:.env.exemplo')
    report['current_artifact_indicators'] = {
        name: sum(len(re.findall(pattern, blob)) for blob in [dump, database, template])
        for name, pattern in patterns.items()
    }
    report['ignore_policy'] = {}
    for path in ['.env', '.env.exemplo', 'db.sqlite3', 'dump.json', 'media/users/b54-policy-probe.png']:
        result = subprocess.run(
            ['git', 'check-ignore', '--no-index', '--quiet', path],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
        )
        report['ignore_policy'][path] = result.returncode == 0
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
