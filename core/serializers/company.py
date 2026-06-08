from rest_framework import serializers
from core.models import User


class CompanyRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'name', 'password']  

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)