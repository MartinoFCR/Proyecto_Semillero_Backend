from django.urls import include, path
from rest_framework import routers
from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


from DjangoProject1.apps.accounts import views

router = routers.DefaultRouter()
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Interfaz Swagger UI
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Interfaz ReDoc
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("admin/", admin.site.urls),

    path("api/accounts/", include(
        "DjangoProject1.apps.accounts.urls"
    )),
    path("api/fleet/", include(
        "DjangoProject1.apps.fleet.urls"
    )),
    path("api/geography/", include(
        "DjangoProject1.apps.geography.urls"
    )),
    path("api/routes/", include(
        "DjangoProject1.apps.routes.urls"
    )),
    path("api/trips/", include(
        "DjangoProject1.apps.trips.urls"
    )),
]
