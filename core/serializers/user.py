from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import User
from core.permissions import account_type

MAX_LATITUDE = 90
MAX_LONGITUDE = 180


class UserSerializer(ModelSerializer):
    tipo = serializers.SerializerMethodField()

    def get_tipo(self, obj):
        return account_type(obj)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
            'profile_image',
            'tipo',
        ]
        read_only_fields = fields
        depth = 1


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    tipo = serializers.ChoiceField(
        choices=[
            ('usuario', 'Usuário'),
            ('empresa', 'Empresa'),
        ],
        write_only=True,
    )

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'password', 'profile_image', 'tipo']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este e-mail já está cadastrado.')
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        validate_password(attrs['password'], User(email=attrs['email'], name=attrs.get('name')))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tipo = validated_data.pop('tipo')
        user = User.objects.create_user(**validated_data)
        if tipo == 'empresa':
            grupo, _ = Group.objects.get_or_create(name='Empresa')
        else:
            grupo, _ = Group.objects.get_or_create(name='Usuário')
        user.groups.add(grupo)

        return user


class UserProfileSerializer(serializers.ModelSerializer):
    precisa_definir_senha = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    tipo = serializers.SerializerMethodField()

    def get_precisa_definir_senha(self, obj) -> bool:
        return not obj.has_usable_password()

    def get_groups(self, obj):
        return UserSerializer(obj).data['groups']

    def get_tipo(self, obj):
        return account_type(obj)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'profile_image',
            'profissao',
            'localizacao',
            'latitude',
            'longitude',
            'geolocation_accuracy',
            'geolocation_timestamp',
            'sobre',
            'telefone',
            'habilidades',
            'perfil_configurado',
            'aviso_perfil_dispensado',
            'precisa_definir_senha',
            'groups',
            'tipo',
        ]
        read_only_fields = [
            'id',
            'email',
            'perfil_configurado',
        ]

    def validate(self, attrs):
        latitude = attrs.get('latitude', self.instance.latitude if self.instance else None)

        longitude = attrs.get('longitude', self.instance.longitude if self.instance else None)

        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError({'localizacao': ('Latitude e longitude devem ser informadas juntas.')})

        if latitude is not None and not -MAX_LATITUDE <= latitude <= MAX_LATITUDE:
            raise serializers.ValidationError({'latitude': 'Latitude inválida.'})

        if longitude is not None and not -MAX_LONGITUDE <= longitude <= MAX_LONGITUDE:
            raise serializers.ValidationError({'longitude': 'Longitude inválida.'})

        return attrs

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        campos_obrigatorios = [
            instance.name,
            instance.profissao,
            instance.localizacao,
            instance.sobre,
            instance.telefone,
        ]
        instance.perfil_configurado = all(campo and str(campo).strip() for campo in campos_obrigatorios)

        instance.save()
        return instance
