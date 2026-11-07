from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.fleet.views import (
    BusViewSet,
    BusTypeViewSet,
    DriverViewSet,
    GPSDeviceViewSet,
    SeatViewSet,
)

router = DefaultRouter()
router.register("buses", BusViewSet, basename="bus")
router.register("bus-types", BusTypeViewSet, basename="bus-type")
router.register("drivers", DriverViewSet, basename="driver")
router.register("devices", GPSDeviceViewSet, basename="gps-device")
router.register("seats", SeatViewSet, basename="seat")

urlpatterns = router.urls