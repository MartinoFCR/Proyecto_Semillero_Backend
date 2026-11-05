from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SupportRequestViewSet

router = DefaultRouter()
router.register("requests", SupportRequestViewSet, basename="support-request")

urlpatterns = [path("", include(router.urls))]
