from rest_framework.permissions import BasePermission


class IsAdminOrSaleOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.role == "admin" or obj.buyer_id == request.user.id
