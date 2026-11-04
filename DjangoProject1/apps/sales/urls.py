from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    AdminSaleView,
    FactusInvoiceRetryView,
    SaleViewSet,
    TicketViewSet,
    WompiCheckoutView,
    WompiTransactionStatusView,
    WompiWebhookView,
)

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls + [
    path("admin-sales/", AdminSaleView.as_view(), name="admin-sale"),
    path(
        "factus/invoices/<int:sale_id>/retry/",
        FactusInvoiceRetryView.as_view(),
        name="factus-invoice-retry",
    ),
    path("wompi/checkout/", WompiCheckoutView.as_view(), name="wompi-checkout"),
    path(
        "wompi/status/",
        WompiTransactionStatusView.as_view(),
        name="wompi-status",
    ),
    path("wompi/webhook/", WompiWebhookView.as_view(), name="wompi-webhook"),
]
