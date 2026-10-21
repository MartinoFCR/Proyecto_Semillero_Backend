from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.geography.views import (
    DepartmentViewSet,
    CityViewSet,
    PlaceViewSet,
)

router = DefaultRouter()
router.register(
    "departments", DepartmentViewSet, basename="department"
)
router.register("cities", CityViewSet, basename="city")
router.register("places", PlaceViewSet, basename="place")

urlpatterns = router.urls