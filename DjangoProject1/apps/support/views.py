from django.core.cache import cache
from django.db import models
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.sales.models import Sale

from .models import SupportRequest
from .serializers import SupportRequestSerializer


class SupportRequestViewSet(ModelViewSet):
    serializer_class = SupportRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        queryset = SupportRequest.objects.select_related(
            "customer",
            "sale",
        ).order_by("-created_at")

        if getattr(user, "role", None) != "admin":
            queryset = queryset.filter(customer=user)

        # Filtros administrativos y de consulta
        status_param = self.request.query_params.get("status")
        category_param = self.request.query_params.get("category")
        search = self.request.query_params.get("search", "").strip()

        if status_param:
            queryset = queryset.filter(status=status_param)
        if category_param:
            queryset = queryset.filter(category=category_param)
        if search:
            queryset = queryset.filter(
                models.Q(subject__icontains=search)
                | models.Q(message__icontains=search)
                | models.Q(customer__username__icontains=search)
                | models.Q(customer__email__icontains=search)
                | models.Q(customer__first_name__icontains=search)
                | models.Q(customer__last_name__icontains=search)
            )

        return queryset

    def create(self, request, *args, **kwargs):
        key = f"support-create:{request.user.pk}"
        if not cache.add(key, True, timeout=60):
            return Response(
                {"code": "rate_limited", "detail": "Espera un minuto antes de crear otra solicitud."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.validated_data.get("sale")
        if sale and sale.buyer_id != request.user.pk:
            return Response(
                {"code": "sale_not_owned", "detail": "La venta no pertenece al cliente."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = serializer.save(customer=request.user)
        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

