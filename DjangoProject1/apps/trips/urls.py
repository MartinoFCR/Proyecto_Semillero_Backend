from rest_framework.routers import DefaultRouter
from django.urls import path
from DjangoProject1.apps.trips.views import (
    AvailableSeatsView,
    TripViewSet,
    TripFareViewSet,
    ReadingViewSet,
    EventViewSet,
    CurrentSeatStateViewSet,
    SeatsStateRecordViewSet,
)

router = DefaultRouter()
router.register("trips", TripViewSet, basename="trip")
router.register("fares", TripFareViewSet, basename="trip-fare")
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
urlpatterns += [
    path(
        "trips/<int:trip_id>/available-seats/",
        AvailableSeatsView.as_view(),
        name="available-seats",
    ),
]