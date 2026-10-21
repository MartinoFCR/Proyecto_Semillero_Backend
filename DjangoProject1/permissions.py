
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    """Solo permite acceso a usuarios con rol admin."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsAdminOrReadOnly(BasePermission):
    """Todos los autenticados pueden leer; admin puede modificar."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return request.user.role == "admin"


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
