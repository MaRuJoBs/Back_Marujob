from rest_framework import serializers

from core.models import Portfolio


class PortfolioSerializer(serializers.ModelSerializer):
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