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
