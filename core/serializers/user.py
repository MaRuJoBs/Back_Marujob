from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


from core.models import User


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_active', 'is_staff', 'is_superuser', 'last_login', 'groups', 'profile_image']
        depth = 1


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    tipo = serializers.ChoiceField(
        choices=[
            ('usuario', 'Usuário'),
            ('empresa', 'Empresa'),
        ],
        write_only=True
    )
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'password', 'profile_image', 'tipo']

    def create(self, validated_data):
        tipo = validated_data.pop('tipo')
        user = User.objects.create_user(**validated_data)
        if tipo == 'empresa':
            grupo = Group.objects.get(name='Empresa')
        else:
            grupo = Group.objects.get(name='Usuário')
        user.groups.add(grupo)
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = [
            'id',
            'email',
            'perfil_configurado',
        ]

    
    def validate(self, attrs):
        latitude = attrs.get(
            'latitude',
            self.instance.latitude if self.instance else None
        )

        longitude = attrs.get(
            'longitude',
            self.instance.longitude if self.instance else None
        )

        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError({
                'localizacao': (
                    'Latitude e longitude devem ser informadas juntas.'
                )
            })

        if latitude is not None and not -90 <= latitude <= 90:
            raise serializers.ValidationError({
                'latitude': 'Latitude inválida.'
            })

        if longitude is not None and not -180 <= longitude <= 180:
            raise serializers.ValidationError({
                'longitude': 'Longitude inválida.'
            })

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
        instance.perfil_configurado = all(
            campo and str(campo).strip() for campo in campos_obrigatorios
        )

        instance.save()
        return instance
