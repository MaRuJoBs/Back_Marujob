import warnings

from cloudinary.exceptions import Error as CloudinaryError
from django.conf import settings
from django.db import transaction
from PIL import Image
from requests.exceptions import RequestException
from rest_framework import serializers
from rest_framework.exceptions import APIException

MAX_LIST_ITEMS = 50
MAX_LIST_ITEM_LENGTH = 100
STORAGE_ERRORS = (OSError, CloudinaryError, RequestException)


class ImageStorageUnavailable(APIException):
    status_code = 503
    default_detail = 'Não foi possível acessar o armazenamento de imagens. Tente novamente.'
    default_code = 'image_storage_unavailable'


class SafeImageStorageMixin:
    def save(self, **kwargs):
        try:
            with transaction.atomic():
                return super().save(**kwargs)
        except STORAGE_ERRORS:
            raise ImageStorageUnavailable() from None


class StringListField(serializers.JSONField):
    """Keep DRF's JSON/multipart decoding, then require an actual string list."""

    def to_internal_value(self, data):
        items = super().to_internal_value(data)
        if not isinstance(items, list) or len(items) > MAX_LIST_ITEMS:
            raise serializers.ValidationError(f'Informe uma lista com até {MAX_LIST_ITEMS} textos.')
        result = []
        for item in items:
            if not isinstance(item, str) or not item.strip() or len(item) > MAX_LIST_ITEM_LENGTH:
                raise serializers.ValidationError(
                    f'Cada item deve ser um texto não vazio com até {MAX_LIST_ITEM_LENGTH} caracteres.'
                )
            normalized = item.strip()
            if normalized not in result:
                result.append(normalized)
        return result


class ValidatedImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if getattr(data, 'size', 0) > settings.MAX_IMAGE_UPLOAD_BYTES:
            raise serializers.ValidationError('A imagem excede o tamanho máximo permitido.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                image = super().to_internal_value(data)
        except (Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise serializers.ValidationError('A imagem possui dimensões excessivas.') from None
        if image.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Use uma imagem JPEG, PNG ou WebP válida.')
        return image

    def to_representation(self, value):
        try:
            return super().to_representation(value)
        except STORAGE_ERRORS:
            raise ImageStorageUnavailable() from None
