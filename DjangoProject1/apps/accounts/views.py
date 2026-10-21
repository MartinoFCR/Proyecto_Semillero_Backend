from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.accounts.models import User
from DjangoProject1.apps.accounts.serializers import UserSerializer
from DjangoProject1.permissions import IsAdminRole


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        # El rol no se acepta desde el serializer público.
        serializer.save()
