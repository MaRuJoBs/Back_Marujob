from rest_framework import mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.models import Favorito
from core.serializers import FavoritoSerializer


class FavoritoViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    serializer_class = FavoritoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorito.objects.filter(usuario=self.request.user).select_related('oportunidade')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        favorito, criado = Favorito.objects.get_or_create(
            usuario=request.user,
            oportunidade=serializer.validated_data['oportunidade'],
        )
        return Response(
            self.get_serializer(favorito).data,
            status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK,
        )
