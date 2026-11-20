from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import serializers

from core.models import EmpresaPerfil, User
from core.serializers.fields import SafeImageStorageMixin, ValidatedImageField
from core.serializers.user import UserProfileSerializer


class LocalizacaoTextoField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError('Informe um texto válido.')
        if any(not character.isprintable() for character in data) or '<' in data or '>' in data:
            raise serializers.ValidationError('Não use marcação ou caracteres de controle na localização.')
        return super().to_internal_value(data)


class EmpresaPerfilSerializer(SafeImageStorageMixin, serializers.ModelSerializer):
    cidade = LocalizacaoTextoField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text='Cidade declarada, sem verificação geográfica. Cidade e UF devem estar juntas.',
    )
    bairro = LocalizacaoTextoField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text='Bairro opcional e privado; não é incluído na consulta pública.',
    )
    pais = serializers.ChoiceField(
        choices=['BR'],
        required=False,
        allow_blank=True,
        help_text='BR, implícito nas UFs brasileiras. Vazio somente quando não há localização completa.',
    )
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
            'pais',
            'bairro',
            'website',
            'contato_comercial',
        ]
        read_only_fields = ['empresa']

    def validate_cidade(self, value):
        if value and not any(character.isalpha() for character in value):
            raise serializers.ValidationError('Informe o nome da cidade.')
        return value

    @staticmethod
    def validate_localizacao(attrs, instance):
        if not {'cidade', 'uf', 'pais', 'bairro'} & attrs.keys():
            return
        cidade = attrs.get('cidade', getattr(instance, 'cidade', ''))
        uf = attrs.get('uf', getattr(instance, 'uf', ''))
        changed = cidade != getattr(instance, 'cidade', '') or uf != getattr(instance, 'uf', '')
        bairro = attrs.get('bairro', '' if changed else getattr(instance, 'bairro', ''))
        errors = {}
        if uf and uf not in dict(EmpresaPerfil._meta.get_field('uf').choices):
            errors['uf'] = 'Informe uma UF brasileira válida.'
        if cidade or uf or bairro or attrs.get('pais'):
            if not cidade:
                errors['cidade'] = 'Informe a cidade junto com a UF.'
            if not uf:
                errors['uf'] = 'Informe a UF junto com a cidade.'
        if 'pais' in attrs and attrs['pais'] != ('BR' if cidade and uf else ''):
            errors['pais'] = 'Use BR para uma localização brasileira ou remova a localização completa.'
        if errors:
            raise serializers.ValidationError(errors)

    def validate(self, attrs):
        self.validate_localizacao(attrs, self.instance)
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        # Lock the existing parent even when this company's institutional row is new.
        company = User.objects.select_for_update().get(pk=instance.empresa_id)
        profile, _ = EmpresaPerfil.objects.get_or_create(empresa=company)
        # Recheck partial updates against the locked, current row, not a stale GET.
        self.validate_localizacao(validated_data, profile)
        changed = any(
            field in validated_data and validated_data[field] != getattr(profile, field) for field in ('cidade', 'uf')
        )
        if changed and 'bairro' not in validated_data:
            validated_data['bairro'] = ''
        validated_data.pop('pais', None)
        company_data = validated_data.pop('empresa', {})
        if company_data:
            # Values are already validated by this serializer. Reuse B40's update
            # so its existing profile-completeness calculation stays consistent.
            UserProfileSerializer(context=self.context).update(company, company_data)
        profile = super().update(profile, validated_data)
        profile.empresa = company
        return profile


class EmpresaLocalizacaoPublicaSerializer(serializers.Serializer):
    cidade = serializers.CharField(read_only=True)
    uf = serializers.CharField(read_only=True)
