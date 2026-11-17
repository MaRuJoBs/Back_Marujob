from django.contrib.auth import get_user_model
from rest_framework import serializers

FALLBACK_NAME = 'Usuário'


def display_name(user):
    """Nome exibido no chat: o nome do perfil; sem ele, "Usuário" (nunca o e-mail)."""
    name = (getattr(user, 'name', '') or '').strip()

    return name or FALLBACK_NAME


class ChatUserSerializer(serializers.ModelSerializer):
    """Identificação pública mínima de um usuário no chat (nunca expõe e-mail, telefone nem permissões)."""

    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    # Profissão do perfil, exibida no cabeçalho da conversa ("@Web-Developer"); '' quando não informada.
    profissao = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'name', 'avatar', 'profissao']
        read_only_fields = fields

    def get_name(self, user) -> str:
        return display_name(user)

    def get_profissao(self, user) -> str:
        return (getattr(user, 'profissao', '') or '').strip()

    def get_avatar(self, user) -> str | None:
        # Foto de perfil enviada pelo usuário (core.User.profile_image), se houver.
        image = user.profile_image

        return image.url if image else None
