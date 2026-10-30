from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.viewsets import ModelViewSet

from core.models import Portfolio
from core.permissions import FreelancerPortfolioPermission
from core.serializers import PortfolioSerializer


class PortfolioViewSet(ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [FreelancerPortfolioPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return Portfolio.objects.filter(usuario=self.request.user).order_by('id')

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
