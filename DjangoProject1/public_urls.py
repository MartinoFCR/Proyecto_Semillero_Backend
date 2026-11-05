from django.urls import path

from DjangoProject1.public_views import (
    PublicRouteListView,
    PublicTripListView,
    CustomerServiceView,
)


urlpatterns = [
    path("routes/", PublicRouteListView.as_view(), name="public-routes"),
    path("trips/", PublicTripListView.as_view(), name="public-trips"),
    path("customer-service/", CustomerServiceView.as_view(), name="customer-service"),
]
