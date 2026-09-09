import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import Group

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser

from core.models import User
from core.serializers import UserRegistrationSerializer, UserSerializer




class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: UserSerializer, 401: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """ Retorna os dados do usuário autenticado."""
        user = request.user
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)



class UserRegistrationView(CreateAPIView):
    """Endpoint para registro de novos usuários."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]


class GoogleLoginView(CreateAPIView):
    """Login/cadastro utilizando uma conta Google."""

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('credential')

        if not token:
            return Response(
                {'detail': 'Token do Google não informado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            google_user = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                os.getenv('GOOGLE_CLIENT_ID'),
            )

        except ValueError:
            return Response(
                {'detail': 'Token do Google inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = google_user.get('email')
        name = google_user.get('name')
        picture = google_user.get('picture')
        email_verified = google_user.get('email_verified', False)

        if not email or not email_verified:
            return Response(
                {'detail': 'O e-mail da conta Google não foi verificado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
            },
        )

        if created:
            if name:
                user.name = name

            user.set_unusable_password()
            user.save()

            # Usuário criado pelo Google começa como usuário comum.
            grupo, _ = Group.objects.get_or_create(name='Usuário')
            user.groups.add(grupo)

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
