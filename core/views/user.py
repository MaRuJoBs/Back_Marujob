import logging
import os
import requests

from django.core.files.base import ContentFile
from django.contrib.auth.models import Group
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User
from core.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    UserProfileSerializer,
)


from rest_framework.viewsets import ReadOnlyModelViewSet


logger = logging.getLogger(__name__)


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna ou atualiza os dados do usuário autenticado.",
        responses={200: UserProfileSerializer, 401: None},
    )
    @action(
        detail=False,
        methods=['get', 'patch'],
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        """Retorna ou atualiza os dados do usuário autenticado."""
        user = request.user

        if request.method == 'PATCH':
            serializer = UserProfileSerializer(
                user,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        serializer = UserProfileSerializer(user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class UserRegistrationView(CreateAPIView):
    """Endpoint para registro de novos usuários."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]


class GoogleLoginView(CreateAPIView):
    """Login e cadastro utilizando uma conta Google."""

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('credential')
        tipo = request.data.get('tipo')
        cadastro = request.data.get('cadastro', False)

        # Verifica se o token foi enviado
        if not isinstance(token, str) or not token.strip():
            return Response(
                {'detail': 'Token do Google não informado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica o tipo de conta
        if cadastro and tipo not in ['usuario', 'empresa']:
            return Response(
                {'detail': 'Tipo de usuário inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Converte string para boolean caso necessário
        if isinstance(cadastro, str):
            cadastro = cadastro.lower() == 'true'

        # Nunca verifica com audience=None: isso desativaria a validacao do Client ID.
        client_id = (os.getenv('GOOGLE_CLIENT_ID') or '').strip()
        if not client_id:
            logger.error('Autenticacao Google sem GOOGLE_CLIENT_ID configurado.')
            return Response(
                {'detail': 'Login com Google temporariamente indisponivel.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            google_user = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=client_id,
                clock_skew_in_seconds=5,
            )
        except TransportError:
            logger.warning('Falha ao consultar os certificados publicos do Google.')
            return Response(
                {'detail': 'Nao foi possivel conectar ao Google. Tente novamente.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (ValueError, GoogleAuthError) as error:
            # A excecao pode conter a credencial: registra somente a categoria.
            message = str(error).lower()
            if 'used too early' in message:
                reason = 'clock_skew'
            elif 'audience' in message:
                reason = 'audience'
            elif 'expired' in message:
                reason = 'expired'
            else:
                reason = 'invalid_token'
            logger.warning('Credencial Google recusada: %s', reason)
            return Response(
                {'detail': 'Token do Google inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Dados fornecidos pelo Google
        email = google_user.get('email')
        name = google_user.get('name')
        google_id = google_user.get('sub')
        profile_image = google_user.get('picture')
        email_verified = google_user.get('email_verified', False)

        # O Google precisa confirmar o e-mail
        if not email or not email_verified:
            return Response(
                {
                    'detail':
                    'O e-mail da conta Google não foi verificado.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Procura um usuário existente pelo e-mail
        user = User.objects.filter(email=email).first()
        if user and not user.is_active:
            return Response(
                {'detail': 'Esta conta esta desativada.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # =========================================================
        # CADASTRO COM GOOGLE
        # =========================================================
        if cadastro:

            # Não permite cadastrar o mesmo e-mail duas vezes
            if user:
                return Response(
                    {
                        'email': [
                            'Este email já está cadastrado.'
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cria o usuário no banco
            user = User.objects.create_user(
                email=email,
                name=name,
            )

            # Conta Google não utiliza senha tradicional
            user.set_unusable_password()

            # Salva o ID único da conta Google
            user.google_id = google_id

            # Salva a foto de perfil do Google
            if profile_image:
                try:
                    imagem = requests.get(
                        profile_image,
                        timeout=10,
                    )

                    if imagem.status_code == 200:
                        user.profile_image.save(
                            'google_profile.jpg',
                            ContentFile(imagem.content),
                            save=False,
                        )
                except requests.RequestException:
                    pass

            user.save()

            # Define o grupo da conta
            if tipo == 'empresa':
                grupo, _ = Group.objects.get_or_create(
                    name='Empresa'
                )
            else:
                grupo, _ = Group.objects.get_or_create(
                    name='Usuário'
                )

            user.groups.add(grupo)

        # =========================================================
        # LOGIN COM GOOGLE
        # =========================================================
        else:

            # A conta precisa existir antes de fazer login
            if not user:
                return Response(
                    {
                        'detail':
                        'Esta conta Google ainda não está cadastrada.'
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Verifica se a conta Google já está vinculada
            if user.google_id:
                if user.google_id != google_id:
                    return Response(
                        {
                            'detail':
                            'Esta conta já está vinculada a outra conta Google.'
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                user.google_id = google_id

            # Salva a foto do Google caso o usuário ainda não tenha foto
            if profile_image and not user.profile_image:
                try:
                    imagem = requests.get(
                        profile_image,
                        timeout=10,
                    )

                    if imagem.status_code == 200:
                        user.profile_image.save(
                            'google_profile.jpg',
                            ContentFile(imagem.content),
                            save=False,
                        )
                except requests.RequestException:
                    pass

            user.save()

        # =========================================================
        # GERA OS TOKENS JWT
        # =========================================================
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'precisa_definir_senha': not user.has_usable_password(),
            },
            status=status.HTTP_200_OK,
        )


class DefinirSenhaView(CreateAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        senha = request.data.get('senha')

        if not senha:
            return Response(
                {'detail': 'A senha é obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(senha) < 8:
            return Response(
                {'detail': 'A senha deve ter pelo menos 8 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(senha)
        request.user.save()

        return Response(
            {'detail': 'Senha definida com sucesso.'},
            status=status.HTTP_200_OK,
        )


class TrocarSenhaView(CreateAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        senha_atual = request.data.get('senha_atual')
        nova_senha = request.data.get('nova_senha')

        if not senha_atual or not nova_senha:
            return Response(
                {'detail': 'Preencha todos os campos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(senha_atual):
            return Response(
                {'detail': 'A senha atual está incorreta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(nova_senha) < 8:
            return Response(
                {'detail': 'A nova senha deve ter pelo menos 8 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(nova_senha)
        request.user.save()

        return Response(
            {'detail': 'Senha alterada com sucesso.'},
            status=status.HTTP_200_OK,
        )