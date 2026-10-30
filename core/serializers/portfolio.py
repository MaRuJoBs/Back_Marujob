from rest_framework import serializers

from core.models import Portfolio
from core.serializers.fields import SafeImageStorageMixin, StringListField, ValidatedImageField


class PortfolioSerializer(SafeImageStorageMixin, serializers.ModelSerializer):
    imagem = ValidatedImageField(required=False, allow_null=True)
    tags = StringListField(required=False)

    class Meta:
        model = Portfolio
        fields = [
            'id',
            'imagem',
            'titulo',
            'categoria',
            'descricao',
            'tags',
            'link',
        ]
        read_only_fields = ['id']
