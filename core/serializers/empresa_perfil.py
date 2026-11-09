from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import serializers

from core.models import EmpresaPerfil, User
from core.serializers.fields import SafeImageStorageMixin, ValidatedImageField
from core.serializers.user import UserProfileSerializer


class EmpresaPerfilSerializer(SafeImageStorageMixin, serializers.ModelSerializer):
    name = serializers.CharField(
        source='empresa.name',
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=255,
    )
    profile_image = ValidatedImageField(source='empresa.profile_image', required=False, allow_null=True)
    website = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=200,
        validators=[URLValidator(schemes=['http', 'https'])],
    )

    class Meta:
        model = EmpresaPerfil
        fields = [
            'empresa',
            'name',
            'profile_image',
            'descricao_institucional',
            'area_atuacao',
            'cidade',
            'uf',
            'website',
            'contato_comercial',
        ]
        read_only_fields = ['empresa']

    @transaction.atomic
    def update(self, instance, validated_data):
        # Lock the existing parent even when this company's institutional row is new.
        company = User.objects.select_for_update().get(pk=instance.empresa_id)
        profile, _ = EmpresaPerfil.objects.get_or_create(empresa=company)
        company_data = validated_data.pop('empresa', {})
        if company_data:
            # Values are already validated by this serializer. Reuse B40's update
            # so its existing profile-completeness calculation stays consistent.
            UserProfileSerializer(context=self.context).update(company, company_data)
        profile = super().update(profile, validated_data)
        profile.empresa = company
        return profile
