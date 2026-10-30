from rest_framework.serializers import ModelSerializer, ValidationError

from core.models import Freelance


class FreelanceSerializer(ModelSerializer):
    class Meta:
        model = Freelance
        fields = '__all__'
        read_only_fields = ['empresa']

    def validate_preco(self, value):
        if value < 0:
            raise ValidationError('O preço não pode ser negativo.')
        return value
