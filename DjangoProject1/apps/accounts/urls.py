from django.urls import path
from rest_framework.routers import DefaultRouter

from DjangoProject1.apps.accounts.views import (
    CustomerDetailView,
    CustomerListCreateView,
    CustomerSearchView,
    ProfileView,
    PublicRegistrationView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls + [
    path("register/", PublicRegistrationView.as_view(), name="register"),
    path("me/", ProfileView.as_view(), name="profile"),
    path(
        "customers/search/",
        CustomerSearchView.as_view(),
        name="customer-search",
    ),
    path(
        "customers/",
        CustomerListCreateView.as_view(),
        name="customer-list-create",
    ),
    path(
        "customers/<int:pk>/",
        CustomerDetailView.as_view(),
        name="customer-detail",
    ),
]
