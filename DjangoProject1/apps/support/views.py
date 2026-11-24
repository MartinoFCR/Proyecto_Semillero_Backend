from django.core.cache import cache
from django.db import models
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.sales.models import Sale

from .models import AuditLog, SupportRequest, SystemErrorLog
from .serializers import (
    AuditLogSerializer,
    SupportRequestSerializer,
    SystemErrorLogSerializer,
)
from rest_framework.viewsets import ReadOnlyModelViewSet


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

        if getattr(user, "role", None) not in {"admin", "seller"}:
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


class SystemErrorLogViewSet(ModelViewSet):
    """Módulo administrativo para auditoría, trazabilidad y resolución de errores del sistema."""
    queryset = SystemErrorLog.objects.all().order_by("-created_at")
    serializer_class = SystemErrorLogSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        # Solo administradores pueden consultar el registro de errores
        if getattr(user, "role", None) != "admin":
            return SystemErrorLog.objects.none()

        queryset = super().get_queryset()
        service_param = self.request.query_params.get("service")
        level_param = self.request.query_params.get("level")
        ref_param = self.request.query_params.get("reference_id")
        resolved_param = self.request.query_params.get("is_resolved")
        search = self.request.query_params.get("search", "").strip()

        if service_param:
            queryset = queryset.filter(service=service_param)
        if level_param:
            queryset = queryset.filter(level=level_param)
        if ref_param:
            queryset = queryset.filter(reference_id__icontains=ref_param)
        if resolved_param is not None:
            val = resolved_param.strip().lower()
            if val in {"true", "1"}:
                queryset = queryset.filter(is_resolved=True)
            elif val in {"false", "0"}:
                queryset = queryset.filter(is_resolved=False)

        if search:
            queryset = queryset.filter(
                models.Q(error_message__icontains=search)
                | models.Q(endpoint__icontains=search)
                | models.Q(reference_id__icontains=search)
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


class AuditLogViewSet(ReadOnlyModelViewSet):
    """Bitácora inmutable de auditoría del sistema. Accesible para admin, auditor, dispatcher y seller."""

    queryset = AuditLog.objects.select_related("actor").all().order_by("-created_at", "-id")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        role = getattr(user, "role", None)
        if role not in {"admin", "auditor", "dispatcher", "seller"}:
            return AuditLog.objects.none()

        queryset = super().get_queryset()
        # Si es vendedor o despachador, puede ver auditoría de viajes y ventas
        if role in {"seller", "dispatcher"}:
            queryset = queryset.filter(module__in=["trips", "sales", "fleet"])

        module_param = self.request.query_params.get("module")
        action_param = self.request.query_params.get("action")
        actor_param = self.request.query_params.get("actor")
        actor_role_param = self.request.query_params.get("actor_role")
        target_model_param = self.request.query_params.get("target_model")
        target_id_param = self.request.query_params.get("target_id")
        search = self.request.query_params.get("search", "").strip()

        if module_param:
            queryset = queryset.filter(module=module_param)
        if action_param:
            queryset = queryset.filter(action__iexact=action_param)
        if actor_param:
            queryset = queryset.filter(actor_id=actor_param)
        if actor_role_param:
            queryset = queryset.filter(actor_role=actor_role_param)
        if target_model_param:
            queryset = queryset.filter(target_model__iexact=target_model_param)
        if target_id_param:
            queryset = queryset.filter(target_id=str(target_id_param))
        if search:
            queryset = queryset.filter(
                models.Q(summary__icontains=search)
                | models.Q(actor_name__icontains=search)
                | models.Q(action__icontains=search)
                | models.Q(target_id__icontains=search)
            )
        return queryset

