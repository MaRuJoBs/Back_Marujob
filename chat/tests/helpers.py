from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.models import Candidatura, Freelance

PASSWORD = 'senha-forte-123'

# Origem do front usada nos testes de WebSocket (liberada via override_settings em CORS_ALLOWED_ORIGINS).
FRONT_ORIGIN = 'https://front.marujob.example'

# PNG 1x1 válido: o tipo real é detectado pelo conteúdo (libmagic), nunca pela extensão.
PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82'
)


def make_user(email, name=None, group=None, **extra):
    user = get_user_model().objects.create_user(email=email, password=PASSWORD, name=name, **extra)

    if group:
        # get_or_create: o TransactionTestCase apaga os grupos criados pela migration entre os testes.
        user.groups.add(Group.objects.get_or_create(name=group)[0])

    return user


def make_freelancer(email, name=None, **extra):
    return make_user(email, name, group='Usuário', **extra)


def make_empresa(email, name=None, **extra):
    return make_user(email, name, group='Empresa', **extra)


def make_vaga(empresa, titulo='Desenvolvedor Vue', **extra):
    defaults = {'preco': 100, 'tempo': '1 mês', 'modalidade': 'Remoto'}

    return Freelance.objects.create(empresa=empresa, titulo=titulo, **{**defaults, **extra})


def make_candidatura(freelancer, vaga, status=Candidatura.Status.PENDENTE):
    return Candidatura.objects.create(freelancer=freelancer, oportunidade=vaga, status=status)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)

    return client


def token_for(user):
    return str(AccessToken.for_user(user))
