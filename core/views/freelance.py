from rest_framework.viewsets import ModelViewSet

from core.models import Freelance
from core.permissions import CompanyOpportunityPermission
from core.serializers import FreelanceSerializer


class FreelanceViewSet(ModelViewSet):
    permission_classes = [CompanyOpportunityPermission]
    queryset = Freelance.objects.all().order_by('id')
    serializer_class = FreelanceSerializer

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user)
