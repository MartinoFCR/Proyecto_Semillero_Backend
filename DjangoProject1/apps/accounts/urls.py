from rest_framework.routers import DefaultRouter
from DjangoProject1.apps.accounts.views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls