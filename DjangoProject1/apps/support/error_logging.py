import logging
import traceback
from typing import Any, Dict, Optional

logger = logging.getLogger("system_error_logger")


def log_system_error(
    service: str,
    error_message: str,
    level: str = "error",
    endpoint: str = "",
    reference_id: str = "",
    error_details: Optional[Any] = None,
    request_payload: Optional[Any] = None,
    response_payload: Optional[Any] = None,
    status_code: Optional[int] = None,
    exc: Optional[Exception] = None,
) -> Any:
    """Registra de manera segura un error del sistema en la base de datos (SystemErrorLog).
    
    Nunca propaga excepciones para no interrumpir el flujo principal de la aplicación.
    """
    from DjangoProject1.apps.support.models import SystemErrorLog

    if exc and not error_details:
        error_details = {
            "exception_type": type(exc).__name__,
            "exception_str": str(exc),
            "traceback": traceback.format_exc(),
        }

    try:
        log_entry = SystemErrorLog.objects.create(
            service=service,
            level=level,
            endpoint=endpoint[:255] if endpoint else "",
            reference_id=str(reference_id)[:80] if reference_id else "",
            error_message=str(error_message)[:2000],
            error_details=error_details,
            request_payload=request_payload,
            response_payload=response_payload,
            status_code=status_code,
        )
        logger.error(
            f"[{service.upper()}] Ref:{reference_id} - {error_message} (ID log: {log_entry.id})"
        )
        return log_entry
    except Exception as save_exc:
        logger.critical(
            f"No se pudo guardar el SystemErrorLog en base de datos: {save_exc}",
            exc_info=True,
        )
        return None
