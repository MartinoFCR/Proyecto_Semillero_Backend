from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    AdminSaleView,
    SaleViewSet,
    TicketViewSet,
    WompiCheckoutView,
    WompiWebhookView,
)

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls + [
    path("admin-sales/", AdminSaleView.as_view(), name="admin-sale"),
    path("wompi/checkout/", WompiCheckoutView.as_view(), name="wompi-checkout"),
    path("wompi/webhook/", WompiWebhookView.as_view(), name="wompi-webhook"),
]
