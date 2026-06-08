from django.contrib.auth.models import Group
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny

from core.models import User
from core.serializers.company import CompanyRegistrationSerializer


class CompanyRegistrationView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = CompanyRegistrationSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()

        grupo, _ = Group.objects.get_or_create(name='Empresa')
        user.groups.add(grupo)