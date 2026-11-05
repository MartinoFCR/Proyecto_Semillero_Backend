from django.urls import path
from rest_framework.routers import DefaultRouter

from DjangoProject1.apps.accounts.views import (
    CustomerDetailView,
    CustomerListCreateView,
    CustomerSearchView,
    ProfileView,
    ProfilePhotoView,
    DigitalCardView,
    CardVerifyView,
    PublicRegistrationView,
    PasswordResetRequestView,
    AccountActivationRequestView,
    AccountActionConfirmView,
    PasswordChangeView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls + [
    path("register/", PublicRegistrationView.as_view(), name="register"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm/",
        AccountActionConfirmView.as_view(purpose="password_reset"),
        name="password-reset-confirm",
    ),
    path(
        "activation/request/",
        AccountActivationRequestView.as_view(),
        name="account-activation-request",
    ),
    path(
        "activation/confirm/",
        AccountActionConfirmView.as_view(purpose="activation"),
        name="account-activation-confirm",
    ),
    path("me/", ProfileView.as_view(), name="profile"),
    path("me/password/", PasswordChangeView.as_view(), name="password-change"),
    path("me/photo/", ProfilePhotoView.as_view(), name="profile-photo"),
    path("me/card/", DigitalCardView.as_view(), name="digital-card"),
    path("cards/verify/", CardVerifyView.as_view(), name="card-verify"),
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
