
from django.db import models
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
    ).all().order_by("origin__place_name", "destination__place_name")
    serializer_class = RouteSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        origin_id = self.request.query_params.get("origin")
        dest_id = self.request.query_params.get("destination")

        if origin_id:
            queryset = queryset.filter(origin_id=origin_id)
        if dest_id:
            queryset = queryset.filter(destination_id=dest_id)
        if search:
            queryset = queryset.filter(
                models.Q(origin__place_name__icontains=search)
                | models.Q(destination__place_name__icontains=search)
                | models.Q(origin__city__city_name__icontains=search)
                | models.Q(destination__city__city_name__icontains=search)
            )
        return queryset
