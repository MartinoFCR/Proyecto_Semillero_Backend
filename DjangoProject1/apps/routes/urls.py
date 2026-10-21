from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.routes.views import RouteViewSet

router = DefaultRouter()
router.register("routes", RouteViewSet, basename="route")

urlpatterns = router.urls