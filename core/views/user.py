import logging

import requests
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User
from core.serializers import (
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)


logger = logging.getLogger(__name__)


class UserViewSet(ReadOnlyModelViewSet):
    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary='Dados do usuário autenticado',
        description='Retorna ou atualiza os dados do usuário autenticado.',
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
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        serializer = UserProfileSerializer(user, context=self.get_serializer_context())

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class UserRegistrationView(CreateAPIView):
    """Endpoint para registro de novos usuários."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise APIValidationError({'email': ['Não foi possível cadastrar esta conta.']}) from None


class GoogleLoginView(CreateAPIView):
    """Login e cadastro utilizando uma conta Google."""

    permission_classes = [AllowAny]
    # Identity comes from the verified Google credential, not an old API JWT.
    authentication_classes = []

    @staticmethod
    @transaction.atomic
    def create_account(email, name, google_id, tipo):
        user = User.objects.create_user(email=email, name=name, google_id=google_id)
        group, _ = Group.objects.get_or_create(name='Empresa' if tipo == 'empresa' else 'Usuário')
        user.groups.add(group)
        return user

    def post(self, request):  # noqa: PLR0911, PLR0912, PLR0915 -- preserve existing OAuth flow
        token = request.data.get('credential')
        tipo = request.data.get('tipo')
        cadastro = request.data.get('cadastro', False)
        if isinstance(cadastro, str):
            cadastro = cadastro.strip().lower()
            if cadastro not in {'true', 'false'}:
                return Response({'detail': 'Informe cadastro como true ou false.'}, status=400)
            cadastro = cadastro == 'true'
        if not isinstance(cadastro, bool) or not isinstance(token, str):
            return Response({'detail': 'Credenciais inválidas.'}, status=400)
        if not settings.GOOGLE_CLIENT_ID:
            return Response({'detail': 'Autenticação Google indisponível.'}, status=503)

        # Verifica se o token foi enviado
        if not token:
            return Response(
                {'detail': 'Token do Google não informado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica o tipo de conta
        if cadastro and (not isinstance(tipo, str) or tipo not in {'usuario', 'empresa'}):
            return Response(
                {'detail': 'Tipo de usuário inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida o token recebido do Google
        try:
            google_user = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=5,
            )

        except TransportError:
            return Response({'detail': 'Autenticação Google indisponível.'}, status=503)
        except (ValueError, GoogleAuthError) as error:
            # Never log the exception itself: it may contain the credential.
            message = str(error).lower()
            if 'used too early' in message:
                reason = 'clock_skew'
            elif 'audience' in message:
                reason = 'audience'
            elif 'expired' in message:
                reason = 'expired'
            else:
                reason = 'invalid_token'
            logger.warning('Google credential rejected: %s', reason)
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
        if not google_id or google_user.get('aud') != settings.GOOGLE_CLIENT_ID:
            return Response({'detail': 'Token do Google inválido.'}, status=400)

        # O Google precisa confirmar o e-mail
        if not email or email_verified is not True:
            return Response(
                {'detail': 'O e-mail da conta Google não foi verificado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Procura um usuário existente pelo e-mail
        matches = User.objects.filter(email__iexact=email)
        if matches.count() > 1:
            return Response({'detail': 'Conta requer revisão administrativa.'}, status=400)
        user = matches.first()
        if user and not user.is_active:
            return Response({'detail': 'Credenciais inválidas.'}, status=401)
        if cadastro and User.objects.filter(google_id=google_id).exists():
            return Response({'detail': 'Conta Google já cadastrada.'}, status=400)

        # =========================================================
        # CADASTRO COM GOOGLE
        # =========================================================
        if cadastro:
            # Não permite cadastrar o mesmo e-mail duas vezes
            if user:
                return Response(
                    {'email': ['Este email já está cadastrado.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cria o usuário no banco
            try:
                user = self.create_account(email, name, google_id, tipo)
            except IntegrityError:
                return Response({'detail': 'Não foi possível cadastrar esta conta.'}, status=400)

            # Salva a foto de perfil do Google
            if profile_image:
                try:
                    imagem = requests.get(
                        profile_image,
                        timeout=10,
                    )

                    if imagem.status_code == status.HTTP_200_OK:
                        user.profile_image.save(
                            'google_profile.jpg',
                            ContentFile(imagem.content),
                            save=False,
                        )
                except requests.RequestException:
                    pass

            user.save()

        # =========================================================
        # LOGIN COM GOOGLE
        # =========================================================
        else:
            # A conta precisa existir antes de fazer login
            if not user:
                return Response(
                    {'detail': 'Esta conta Google ainda não está cadastrada.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Verifica se a conta Google já está vinculada
            if user.google_id:
                if user.google_id != google_id:
                    return Response(
                        {'detail': 'Esta conta já está vinculada a outra conta Google.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {'detail': 'Entre com sua senha. Vinculação Google requer confirmação da conta.'},
                    status=400,
                )

            # Salva a foto do Google caso o usuário ainda não tenha foto
            if profile_image and not user.profile_image:
                try:
                    imagem = requests.get(
                        profile_image,
                        timeout=10,
                    )

                    if imagem.status_code == status.HTTP_200_OK:
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
        if request.user.has_usable_password() or not request.user.google_id:
            return Response({'detail': 'Utilize a troca de senha com a senha atual.'}, status=400)
        senha = request.data.get('senha')

        if not senha:
            return Response(
                {'detail': 'A senha é obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if not isinstance(senha, str):
                raise ValidationError('Senha inválida.')
            validate_password(senha, request.user)
        except ValidationError as exc:
            return Response(
                {'senha': exc.messages},
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

        if not isinstance(senha_atual, str) or not senha_atual or not nova_senha:
            return Response(
                {'detail': 'Preencha todos os campos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(senha_atual):
            return Response(
                {'detail': 'A senha atual está incorreta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if not isinstance(nova_senha, str):
                raise ValidationError('Senha inválida.')
            validate_password(nova_senha, request.user)
        except ValidationError as exc:
            return Response(
                {'nova_senha': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(nova_senha)
        request.user.save()

        return Response(
            {'detail': 'Senha alterada com sucesso.'},
            status=status.HTTP_200_OK,
        )
