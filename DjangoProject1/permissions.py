
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    """Solo permite acceso a usuarios con rol admin."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class PasswordChangeRequiredPermission(BasePermission):
    allowed_paths = (
        "/api/accounts/me/",
        "/api/accounts/me/password/",
        "/api/accounts/me/photo/",
        "/api/accounts/me/card/",
        "/api/accounts/logout/",
    )

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == "admin" or not user.password_change_required:
            return True
        return request.path.rstrip("/") in {
            path.rstrip("/") for path in self.allowed_paths
        }


class IsAdminOrReadOnly(BasePermission):
    """Todos los autenticados pueden leer; admin puede modificar."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return request.user.role == "admin"


class IsAdminOrOwnDriver(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {"admin", "driver"}
        )

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == "admin"
            or getattr(obj, "user_id", None) == request.user.id
        )


class IsAdminOrAssignedDriver(BasePermission):
    """
    Permite al administrador o al conductor asignado
    acceder a un viaje.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True

        driver_profile = getattr(
            request.user, "driver_profile", None
        )

        if driver_profile is None:
            return False

        trip = getattr(obj, "trip", obj)

        return (
            hasattr(trip, "driver_id")
            and trip.driver_id == driver_profile.pk
        )


class IsAdminOrAssignedDriverReadOnly(BasePermission):
    """
    El administrador puede gestionar viajes.
    El conductor asignado solo puede consultarlos.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True

        if request.method not in SAFE_METHODS:
            return False

        driver_profile = getattr(
            request.user, "driver_profile", None
        )

        return bool(
            driver_profile
            and obj.driver_id == driver_profile.pk
        )
