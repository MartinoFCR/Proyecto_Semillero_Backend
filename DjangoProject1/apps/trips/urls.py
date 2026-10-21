from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.trips.views import (
    TripViewSet,
    ReadingViewSet,
    EventViewSet,
    CurrentSeatStateViewSet,
    SeatsStateRecordViewSet,
)

router = DefaultRouter()
router.register("trips", TripViewSet, basename="trip")
router.register("readings", ReadingViewSet, basename="reading")
router.register("events", EventViewSet, basename="event")
router.register(
    "current-seat-states",
    CurrentSeatStateViewSet,
    basename="current-seat-state",
)
router.register(
    "seat-state-history",
    SeatsStateRecordViewSet,
    basename="seat-state-history",
)

urlpatterns = router.urls