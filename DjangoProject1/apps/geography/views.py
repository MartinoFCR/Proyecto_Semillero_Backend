
from rest_framework.viewsets import ModelViewSet

from .models import (
    Department,
    City,
    Place,
)
from .serializers import (
    DepartmentSerializer,
    CitySerializer,
    PlaceSerializer,
)
from DjangoProject1.permissions import IsAdminOrReadOnly


class DepartmentViewSet(ModelViewSet):
    queryset = Department.objects.all().order_by("department_name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]


class CityViewSet(ModelViewSet):
    queryset = City.objects.select_related("department").all()
    serializer_class = CitySerializer
    permission_classes = [IsAdminOrReadOnly]


class PlaceViewSet(ModelViewSet):
    queryset = Place.objects.select_related(
        "city",
        "city__department",
    ).all()
    serializer_class = PlaceSerializer
    permission_classes = [IsAdminOrReadOnly]
