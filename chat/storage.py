"""Private chat uploads. Signed download URLs stay inside the backend."""

import time
from http import HTTPStatus
from pathlib import PurePosixPath

import cloudinary.uploader
import cloudinary.utils
import requests
from cloudinary_storage.storage import RawMediaCloudinaryStorage
from django.conf import settings
from django.core.files.base import ContentFile


class AuthenticatedChatStorage(RawMediaCloudinaryStorage):
    def _upload(self, name, content):
        return cloudinary.uploader.upload(
            content,
            use_filename=True,
            resource_type='raw',
            type='authenticated',
            tags=self.TAG,
            folder=str(PurePosixPath(name).parent),
        )

    def url(self, name):
        raise ValueError('Anexos do chat são acessados somente pela API autenticada.')

    def _get_url(self, name):
        return cloudinary.utils.private_download_url(
            self._prepend_prefix(name),
            '',
            resource_type='raw',
            type='authenticated',
            expires_at=int(time.time()) + 60,
        )

    def _open(self, name, mode='rb'):
        name = self._prepend_prefix(name)
        # Older uploads used type=upload. Read them only through the authorized
        # API until their access type is changed in a separate operational step.
        for delivery_type in ('authenticated', 'upload'):
            url = cloudinary.utils.private_download_url(
                name,
                '',
                resource_type='raw',
                type=delivery_type,
                expires_at=int(time.time()) + 60,
            )
            with requests.get(url, timeout=10, stream=True, allow_redirects=False) as response:
                if response.status_code == HTTPStatus.NOT_FOUND:
                    continue
                if response.status_code != HTTPStatus.OK:
                    raise OSError('Anexo indisponível.')
                chunks = bytearray()
                limit = settings.CHAT_MAX_UPLOAD_MB * 1024 * 1024
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if len(chunks) + len(chunk) > limit:
                        raise OSError('Anexo excede o limite permitido.')
                    chunks.extend(chunk)
                return ContentFile(bytes(chunks), name=name)
        raise FileNotFoundError('Anexo não encontrado.')

    def delete(self, name):
        for delivery_type in ('authenticated', 'upload'):
            result = cloudinary.uploader.destroy(
                name,
                invalidate=True,
                resource_type='raw',
                type=delivery_type,
            )
            if result['result'] == 'ok':
                return True
        return False
