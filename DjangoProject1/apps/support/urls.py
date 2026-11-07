from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SupportRequestViewSet, SystemErrorLogViewSet

router = DefaultRouter()
router.register("requests", SupportRequestViewSet, basename="support-request")
router.register("errors", SystemErrorLogViewSet, basename="system-error-log")

urlpatterns = [path("", include(router.urls))]
