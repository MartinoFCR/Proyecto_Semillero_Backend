from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.fleet.views import (
    BusViewSet,
    DriverViewSet,
    SeatViewSet,
)

router = DefaultRouter()
router.register("buses", BusViewSet, basename="bus")
router.register("drivers", DriverViewSet, basename="driver")
router.register("seats", SeatViewSet, basename="seat")

urlpatterns = router.urls