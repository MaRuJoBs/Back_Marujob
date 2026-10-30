from rest_framework import serializers

from core.models import Favorito, Freelance
from core.serializers.freelance import FreelanceSerializer


class FavoritoSerializer(serializers.ModelSerializer):
    oportunidade = serializers.PrimaryKeyRelatedField(queryset=Freelance.objects.all())
    oportunidade_detalhes = FreelanceSerializer(source='oportunidade', read_only=True)

    class Meta:
        model = Favorito
        fields = ['id', 'oportunidade', 'oportunidade_detalhes', 'criado_em']
        read_only_fields = ['id', 'criado_em']
        # A unicidade é tratada por get_or_create e pela constraint do banco.
        validators = []
