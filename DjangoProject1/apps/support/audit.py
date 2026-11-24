from typing import Any, Optional
from .models import AuditLog

ROLE_LABELS = {
    "admin": "Administrador",
    "seller": "Vendedor",
    "dispatcher": "Despachador",
    "driver": "Conductor",
    "auditor": "Auditor",
    "client": "Cliente",
    "system": "Sistema Automático",
}


def format_user_attribution(user) -> tuple[str, str, str]:
    """Devuelve (role_code, role_label, full_display_name) de un usuario o conductor."""
    if not user or not getattr(user, "is_authenticated", False):
        return "system", "Sistema Automático", "Sistema Automático"

    role_code = getattr(user, "role", "client") or "client"
    role_label = ROLE_LABELS.get(role_code, role_code.capitalize())

    driver_profile = getattr(user, "driver_profile", None)
    if driver_profile and getattr(driver_profile, "full_name", ""):
        full_name = driver_profile.full_name.strip()
    else:
        full_name = " ".join(
            part for part in (getattr(user, "first_name", ""), getattr(user, "last_name", "")) if part
        ).strip()
        if not full_name:
            full_name = getattr(user, "username", "Usuario")

    return role_code, role_label, full_name


def build_att_signature(user) -> str:
    """Construye la firma 'ATT: <Rol> <Nombre>' para mostrar en viajes y registros."""
    role_code, role_label, full_name = format_user_attribution(user)
    if role_code == "system":
        return "ATT: Sistema Automático"
    return f"ATT: {role_label} {full_name}"


def get_client_ip(request) -> Optional[str]:
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_audit_event(
    *,
    actor=None,
    request=None,
    module: str,
    action: str,
    summary: str,
    target_model: str = "",
    target_id: Any = "",
    previous_data: Optional[dict] = None,
    new_data: Optional[dict] = None,
) -> Optional[AuditLog]:
    """Registra de forma segura un evento en la bitácora inmutable AuditLog."""
    try:
        if actor is None and request is not None:
            user = getattr(request, "user", None)
            if user and getattr(user, "is_authenticated", False):
                actor = user

        role_code, role_label, full_name = format_user_attribution(actor)
        actor_display = (
            f"{role_label} {full_name}"
            if role_code != "system"
            else "Sistema Automático"
        )
        ip = get_client_ip(request)

        return AuditLog.objects.create(
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            actor_name=actor_display[:160],
            actor_role=role_code[:30],
            module=module,
            action=action[:60],
            target_model=str(target_model)[:60],
            target_id=str(target_id)[:60] if target_id is not None else "",
            summary=summary,
            previous_data=previous_data,
            new_data=new_data,
            ip_address=ip,
        )
    except Exception:
        return None
