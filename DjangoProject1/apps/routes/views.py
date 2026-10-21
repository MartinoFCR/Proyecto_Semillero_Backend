
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.routes.serializers import RouteSerializer
from DjangoProject1.permissions import IsAdminOrReadOnly


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.select_related(
        "origin",
        "destination",
        "origin__city",
        "destination__city",
    ).all()
    serializer_class = RouteSerializer
    permission_classes = [IsAdminOrReadOnly]
