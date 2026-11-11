"""Best-effort optional Google photo; identity must already be verified."""

import logging
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.exceptions import ValidationError

from core.serializers.fields import STORAGE_ERRORS, ValidatedImageField

logger = logging.getLogger(__name__)
PHOTO_CHUNK_BYTES = 64 * 1024


def attach_google_photo(user, url):
    """A missing/invalid photo must not prevent a verified login or registration."""
    previous = user.profile_image.name
    try:
        if not isinstance(url, str):
            return
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return
        # No redirect following: the destination comes only from verified claims.
        with requests.get(url, timeout=10, stream=True, allow_redirects=False) as response:
            if response.status_code != status.HTTP_200_OK:
                return
            content = bytearray()
            for chunk in response.iter_content(chunk_size=PHOTO_CHUNK_BYTES):
                if len(content) + len(chunk) > settings.MAX_IMAGE_UPLOAD_BYTES:
                    return
                content.extend(chunk)
        image = ValidatedImageField().run_validation(SimpleUploadedFile('google_profile.jpg', bytes(content)))
        extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[image.image.format]
        user.profile_image.save(f'google_profile.{extension}', image, save=False)
    except (ValidationError, DjangoValidationError, ValueError, *STORAGE_ERRORS):
        user.profile_image = previous
        # Never log the URL, provider response, exception or credential.
        logger.warning('Optional Google photo unavailable')
