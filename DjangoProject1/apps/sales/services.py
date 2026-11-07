import hashlib
import hmac
import json
import logging
import os
from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.mail import EmailMultiAlternatives
from smtplib import SMTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from DjangoProject1.apps.fleet.models import Seat

from .models import FactusInvoice, Payment, Sale, SaleItem, Ticket

logger = logging.getLogger(__name__)
User = get_user_model()


def create_ticket_for_sale(sale, trip, seat, passenger):
    if seat.bus_id != trip.bus_id:
        raise ValidationError({"seat": "La silla no pertenece al bus del viaje."})

    existing_ticket = Ticket.objects.filter(
        trip=trip,
        seat=seat,
        status=Ticket.Status.ISSUED,
    ).first()
    if existing_ticket:
        if existing_ticket.sale_id == sale.pk:
            return existing_ticket
        raise ValidationError({"seat": "La silla ya está vendida para este viaje."})

    return Ticket.objects.create(
        sale=sale,
        trip=trip,
        seat=seat,
        passenger_identification=passenger["identification_number"],
        passenger_identification_document_code=passenger.get(
            "identification_document_code",
            "",
        ),
        passenger_name=passenger["name"],
        passenger_email=passenger["email"],
        passenger_telephone=passenger.get("telephone", ""),
    )


def _sale_items(sale):
    items = list(sale.items.select_related("trip", "seat"))
    if items:
        return items
    return [
        SaleItem(
            sale=sale,
            trip=sale.trip,
            seat=sale.seat,
            passenger_identification=sale.passenger_identification,
            passenger_identification_document_code=(
                sale.passenger_identification_document_code
            ),
            passenger_name=sale.passenger_name,
            passenger_email=sale.passenger_email,
            passenger_telephone=sale.passenger_telephone,
        )
    ]


def _seats_taken_by_others(sale, items):
    """Devuelve los IDs de sillas vendidas o reservadas por otra venta.

    Debe llamarse dentro de una transacción. Bloquea las sillas en el mismo
    orden que el checkout para evitar condiciones de carrera.
    """
    seat_ids = sorted({item.seat_id for item in items})
    list(Seat.objects.select_for_update().filter(pk__in=seat_ids).order_by("pk"))
    taken = set(
        Ticket.objects.filter(
            trip_id=sale.trip_id,
            seat_id__in=seat_ids,
            status=Ticket.Status.ISSUED,
        ).exclude(sale=sale).values_list("seat_id", flat=True)
    )
    active_holds = Sale.objects.filter(
        trip_id=sale.trip_id,
        source=Sale.Source.ONLINE,
        status=Sale.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).exclude(pk=sale.pk).filter(
        Q(seat_id__in=seat_ids) | Q(items__seat_id__in=seat_ids)
    ).prefetch_related("items")
    for hold in active_holds:
        held = {hold.seat_id} | {item.seat_id for item in hold.items.all()}
        taken.update(held.intersection(seat_ids))
    return taken


def notify_refund_required(sale_id):
    """Avisa a los administradores que un pago aprobado no tiene silla."""
    sale = Sale.objects.select_related("buyer", "payment").get(pk=sale_id)
    recipients = list(
        User.objects.filter(role=User.Role.ADMIN, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    logger.error(
        "Venta %s pagada en Wompi sin sillas disponibles: requiere reembolso.",
        sale.pk,
    )
    if not recipients:
        logger.warning("No hay administradores con correo para avisar.")
        return False
    reference = getattr(getattr(sale, "payment", None), "provider_reference", "")
    body = (
        f"La venta #{sale.pk} fue pagada en Wompi después de vencer la "
        "reserva y una o más sillas ya estaban ocupadas, por lo que no se "
        "emitieron tiquetes.\n\n"
        f"Comprador: {sale.buyer.get_full_name() or sale.buyer.username} "
        f"({sale.buyer.email})\n"
        f"Valor: ${sale.amount_cents / 100:,.2f} COP\n"
        f"Referencia Wompi: {reference}\n\n"
        "Acción requerida: contactar al cliente para reubicarlo o realizar "
        "el reembolso desde el panel de Wompi."
    )
    try:
        EmailMultiAlternatives(
            subject=f"[Acción requerida] Reembolso venta #{sale.pk}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        ).send(fail_silently=False)
    except (SMTPException, OSError):
        logger.exception("No se pudo enviar el aviso de reembolso.")
        return False
    return True


def mark_sale_paid(sale, payment_status, provider_reference, raw_response):
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        if sale.status in {Sale.Status.PAID, Sale.Status.REFUND_REQUIRED}:
            return sale
        is_expired = sale.status == Sale.Status.EXPIRED or (
            sale.status == Sale.Status.PENDING
            and sale.expires_at
            and sale.expires_at <= timezone.now()
        )
        # El pago siempre se registra, aunque la reserva haya vencido.
        payment, _ = Payment.objects.select_for_update().get_or_create(
            sale=sale,
            defaults={
                "amount_cents": sale.amount_cents,
                "provider": "wompi",
            },
        )
        payment.status = payment_status
        if provider_reference:
            payment.provider_reference = provider_reference
        payment.raw_response = raw_response
        payment.processed_at = timezone.now()
        payment.save()

        if payment_status != "APPROVED":
            sale.status = (
                Sale.Status.EXPIRED if is_expired else Sale.Status.FAILED
            )
            sale.save(update_fields=["status", "updated_at"])
            return sale

        items = _sale_items(sale)
        if is_expired:
            taken = _seats_taken_by_others(sale, items)
            if taken:
                sale.status = Sale.Status.REFUND_REQUIRED
                sale.save(update_fields=["status", "updated_at"])
                transaction.on_commit(
                    lambda sale_id=sale.pk: notify_refund_required(sale_id)
                )
                return sale
            logger.info(
                "Venta %s pagada tras vencer la reserva; sillas libres, "
                "se emiten tiquetes.",
                sale.pk,
            )

        sale.status = Sale.Status.PAID
        sale.save(update_fields=["status", "updated_at"])
        for item in items:
            create_ticket_for_sale(
                sale,
                item.trip,
                item.seat,
                {
                    "identification_number": item.passenger_identification,
                    "identification_document_code": (
                        item.passenger_identification_document_code
                    ),
                    "name": item.passenger_name,
                    "email": item.passenger_email,
                    "telephone": item.passenger_telephone,
                },
            )
        transaction.on_commit(
            lambda sale_id=sale.pk: issue_factus_invoice(sale_id)
        )
        transaction.on_commit(
            lambda sale_id=sale.pk: send_sale_confirmation_email(sale_id)
        )
        return sale


def send_sale_confirmation_email(sale_id, force=False):
    with transaction.atomic():
        sale = Sale.objects.select_for_update().select_related(
            "buyer",
            "trip__route__origin",
            "trip__route__destination",
        ).prefetch_related("items", "tickets").get(pk=sale_id)
        if sale.status != Sale.Status.PAID:
            return False
        if sale.email_confirmation_sent_at and not force:
            return False
        tickets = list(sale.tickets.select_related("seat").all())
        lines = [
            f"- {ticket.passenger_name}, silla {ticket.seat.seat_number}, "
            f"tiquete {ticket.ticket_code}"
            for ticket in tickets
        ]
        body = (
            f"Compra #{sale.pk} confirmada.\n\n"
            f"Total pagado: ${sale.amount_cents / 100:,.2f} COP\n"
            f"Ruta: {sale.trip.route.origin.place_name} -> "
            f"{sale.trip.route.destination.place_name}\n"
            f"Salida: {sale.trip.date_time_start}\n\n"
            "Boletas:\n" + "\n".join(lines) +
            f"\n\nIngresa a {settings.FRONTEND_BASE_URL}/clientes/compras "
            "para consultar la factura y descargar tus boletas."
        )
        message = EmailMultiAlternatives(
            subject=f"Confirmación de compra #{sale.pk}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[sale.buyer.email],
        )
        try:
            message.send(fail_silently=False)
        except (SMTPException, OSError):
            return False
        sale.email_confirmation_sent_at = timezone.now()
        sale.save(update_fields=["email_confirmation_sent_at", "updated_at"])
        return True


def get_wompi_transaction(transaction_id):
    base_url = os.getenv(
        "WOMPI_BASE_URL",
        "https://sandbox.wompi.co/v1",
    ).rstrip("/")
    private_key = os.getenv("WOMPI_PRIVATE_KEY")
    if not private_key:
        raise ValidationError("WOMPI_PRIVATE_KEY no está configurada.")

    request = Request(
        f"{base_url}/transactions/{transaction_id}",
        headers={
            "Authorization": "Bearer " + private_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValidationError(
            {"transaction_id": "Wompi rechazó la consulta de la transacción."}
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValidationError(
            {"transaction_id": "No fue posible consultar Wompi en este momento."}
        ) from exc


def wompi_expiration_time(value):
    """Formatea una fecha como la espera Wompi: UTC ISO 8601 con milisegundos."""
    value = value.astimezone(dt_timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def wompi_integrity_signature(
    reference,
    amount_cents,
    currency="COP",
    expiration_time="",
):
    secret = os.getenv("WOMPI_INTEGRITY_SECRET")
    if not secret:
        raise ValidationError("WOMPI_INTEGRITY_SECRET no está configurado.")
    payload = f"{reference}{amount_cents}{currency}{expiration_time}{secret}"
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_wompi_event_signature(payload):
    events_secret = os.getenv("WOMPI_EVENTS_SECRET")
    if not events_secret:
        return False

    if not isinstance(payload, dict):
        return False
    event = payload.get("event")
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return False
    signature = data.get("signature", {})
    if not isinstance(signature, dict):
        return False
    timestamp = payload.get("timestamp")
    properties = signature.get("properties")
    transaction = data.get("transaction", {})
    expected_properties = (
        "transaction.id",
        "transaction.status",
        "transaction.amount_in_cents",
        "transaction.currency",
        "transaction.reference",
    )
    if (
        event != "transaction.updated"
        or not isinstance(timestamp, (int, str))
        or tuple(properties or ()) != expected_properties
        or not isinstance(transaction, dict)
        or not signature.get("checksum")
    ):
        return False

    values = "".join(
        str(transaction.get(prop.split(".", 1)[1], ""))
        for prop in expected_properties
    )
    expected = hashlib.sha256(
        f"{values}{timestamp}{events_secret}".encode()
    ).hexdigest()
    return hmac.compare_digest(signature["checksum"], expected)


def _factus_configuration():
    names = (
        "FACTUS_BASE_URL",
        "FACTUS_USERNAME",
        "FACTUS_PASSWORD",
        "FACTUS_CLIENT_ID",
        "FACTUS_CLIENT_SECRET",
        "FACTUS_NUMBERING_RANGE_ID",
        "FACTUS_MUNICIPALITY_CODE",
        "FACTUS_PRODUCT_CODE",
        "FACTUS_PRODUCT_NAME",
        "FACTUS_UNIT_MEASURE_CODE",
        "FACTUS_STANDARD_CODE",
        "FACTUS_TAX_CODE",
        "FACTUS_TAX_RATE",
        "FACTUS_TAX_EXCLUDED",
    )
    return {name: os.getenv(name, "").strip() for name in names}


def _factus_token(config):
    boundary = "----FactusBoundary"
    fields = {
        "grant_type": "password",
        "username": config["FACTUS_USERNAME"],
        "password": config["FACTUS_PASSWORD"],
        "client_id": config["FACTUS_CLIENT_ID"],
        "client_secret": config["FACTUS_CLIENT_SECRET"],
    }
    parts = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                ).encode(),
                f"{value}\r\n".encode(),
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    request = Request(
        f"{config['FACTUS_BASE_URL'].rstrip('/')}/oauth/token",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValidationError(
            "Factus no pudo autenticar la solicitud."
        ) from exc
    token = result.get("access_token")
    if not token:
        raise ValidationError("Factus no devolvió un token de acceso.")
    return token


def factus_token_diagnostics():
    config = _factus_configuration()
    required = (
        "FACTUS_BASE_URL",
        "FACTUS_USERNAME",
        "FACTUS_PASSWORD",
        "FACTUS_CLIENT_ID",
        "FACTUS_CLIENT_SECRET",
    )
    missing = [name for name in required if not config[name]]
    if missing:
        return {
            "ok": False,
            "missing": missing,
            "response_fields": [],
        }

    boundary = "----FactusDiagnosticBoundary"
    fields = {
        "grant_type": "password",
        "username": config["FACTUS_USERNAME"],
        "password": config["FACTUS_PASSWORD"],
        "client_id": config["FACTUS_CLIENT_ID"],
        "client_secret": config["FACTUS_CLIENT_SECRET"],
    }
    parts = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                ).encode(),
                f"{value}\r\n".encode(),
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode())
    request = Request(
        f"{config['FACTUS_BASE_URL'].rstrip('/')}/oauth/token",
        data=b"".join(parts),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            return {
                "ok": bool(response_data.get("access_token")),
                "http_status": response.status,
                "response_fields": sorted(response_data.keys()),
                "token_type": response_data.get("token_type"),
                "expires_in": response_data.get("expires_in"),
                "has_access_token": bool(response_data.get("access_token")),
                "has_refresh_token": bool(response_data.get("refresh_token")),
            }
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            error_fields = sorted(body.keys())
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_fields = []
        return {
            "ok": False,
            "http_status": exc.code,
            "response_fields": error_fields,
        }
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "response_fields": [],
        }


def factus_invoice_diagnostics():
    config = _factus_configuration()
    token = _factus_token(config)
    payload = {
        "reference_code": "FACT-2026-0124",
        "document": "01",
        "numbering_range_id": 389,
        "operation_type": "10",
        "observation": "Observación de prueba",
        "payment_details": [
            {
                "payment_form": "1",
                "payment_method_code": "42",
                "reference_code": "pago-001",
                "amount": "83300",
            }
        ],
        "cash_rounding_amount": "0.00",
        "customer": {
            "identification_document_code": "31",
            "identification": "123456789",
            "company": "Alan company name",
            "trade_name": "Alan trade name",
            "address": "calle 1 # 1-1",
            "email": "alan.company@email.com",
            "phone": "1234567890",
            "legal_organization_code": "1",
            "tribute_code": "ZZ",
            "country_code": "CO",
            "responsibilities": ["R-99-PN"],
            "municipality_code": "68679",
        },
        "items": [
            {
                "code_reference": "PROD-000A",
                "name": "Producto A",
                "quantity": "1.00",
                "discount_rate": "0.00",
                "price": "10000.00",
                "unit_measure_code": "94",
                "standard_code": "999",
                "taxes": [{"code": "01", "rate": "19.00"}],
            },
            {
                "code_reference": "PROD-000B",
                "name": "Producto B",
                "quantity": "3.00",
                "discount_rate": "0.00",
                "price": "20000.00",
                "unit_measure_code": "94",
                "standard_code": "999",
                "taxes": [{"code": "01", "rate": "19.00"}],
            },
        ],
    }
    request = Request(
        f"{config['FACTUS_BASE_URL'].rstrip('/')}/v2/bills/validate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SemilleroBackend/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return {
                "ok": True,
                "http_status": response.status,
                "response": json.loads(body),
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            response = json.loads(body)
        except json.JSONDecodeError:
            response = {"raw_body": body}
        return {
            "ok": False,
            "http_status": exc.code,
            "response": response,
        }


def _factus_invoice_payload(sale, config):
    price = sale.amount_cents / 100
    payment_methods = {
        Sale.PaymentMethod.CASH: "10",
        Sale.PaymentMethod.TRANSFER: "47",
        Sale.PaymentMethod.CARD: "48",
        Sale.PaymentMethod.WOMPI: "48",
    }
    items = list(sale.items.all())
    if not items:
        items = [
            SaleItem(
                trip=sale.trip,
                seat=sale.seat,
                passenger_identification=sale.passenger_identification,
                passenger_identification_document_code=(
                    sale.passenger_identification_document_code
                ),
                passenger_name=sale.passenger_name,
                passenger_email=sale.passenger_email,
                passenger_telephone=sale.passenger_telephone,
            )
        ]
    payload = {
        "reference_code": f"SALE-{sale.pk}",
        "document": "01",
        "operation_type": "10",
        "send_email": False,
        "observation": f"Transporte - venta {sale.pk}",
        "cash_rounding_amount": "0.00",
        "payment_details": [
            {
                "payment_form": "1",
                "payment_method_code": payment_methods[sale.payment_method],
                "reference_code": f"SALE-{sale.pk}",
                "amount": f"{price:.2f}",
            }
        ],
        "customer": {
            "identification_document_code": (
                items[0].passenger_identification_document_code or "13"
            ),
            "identification": sale.passenger_identification,
            "legal_organization_code": "2",
            "tribute_code": "ZZ",
            "responsibilities": ["R-99-PN"],
            "names": sale.passenger_name,
            "email": sale.passenger_email,
            "phone": sale.passenger_telephone,
            "country_code": "CO",
        },
        "items": [
            {
                "code_reference": config["FACTUS_PRODUCT_CODE"],
                "name": (
                    f"{config['FACTUS_PRODUCT_NAME']} - "
                    f"silla {item.seat.seat_number}"
                ),
                "quantity": "1",
                "discount_rate": "0.00",
                "price": f"{(
                    sale.amount_cents // len(items)
                    + (index < sale.amount_cents % len(items))
                ) / 100:.2f}",
                "unit_measure_code": config["FACTUS_UNIT_MEASURE_CODE"],
                "standard_code": config["FACTUS_STANDARD_CODE"],
                "taxes": [
                    {
                        "code": config["FACTUS_TAX_CODE"],
                        "rate": config["FACTUS_TAX_RATE"],
                        "is_excluded": (
                            config["FACTUS_TAX_EXCLUDED"].lower()
                            in {"1", "true", "yes", "on"}
                        ),
                    }
                ],
            }
            for index, item in enumerate(items)
        ],
    }
    if config["FACTUS_MUNICIPALITY_CODE"]:
        payload["customer"]["municipality_code"] = (
            config["FACTUS_MUNICIPALITY_CODE"]
        )
    if config["FACTUS_NUMBERING_RANGE_ID"]:
        payload["numbering_range_id"] = int(config["FACTUS_NUMBERING_RANGE_ID"])
    return payload


def issue_factus_invoice(sale_id):
    sale = Sale.objects.select_related("trip").get(pk=sale_id)
    invoice, _ = FactusInvoice.objects.get_or_create(sale=sale)
    if invoice.status == FactusInvoice.Status.ISSUED:
        return invoice

    config = _factus_configuration()
    required = (
        "FACTUS_BASE_URL",
        "FACTUS_USERNAME",
        "FACTUS_PASSWORD",
        "FACTUS_CLIENT_ID",
        "FACTUS_CLIENT_SECRET",
        "FACTUS_PRODUCT_CODE",
        "FACTUS_PRODUCT_NAME",
        "FACTUS_UNIT_MEASURE_CODE",
        "FACTUS_STANDARD_CODE",
        "FACTUS_TAX_CODE",
        "FACTUS_TAX_RATE",
        "FACTUS_TAX_EXCLUDED",
    )
    missing = [name for name in required if not config[name]]
    if missing:
        invoice.status = FactusInvoice.Status.ERROR
        invoice.error_message = (
            "Faltan variables de configuración fiscal: " + ", ".join(missing)
        )
        invoice.save(update_fields=["status", "error_message", "updated_at"])
        return invoice

    try:
        token = _factus_token(config)
        payload = _factus_invoice_payload(sale, config)
        request = Request(
            f"{config['FACTUS_BASE_URL'].rstrip('/')}/v2/bills/validate",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "SemilleroBackend/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        raw_body_data = None
        try:
            raw_text = exc.read().decode("utf-8")
            raw_body_data = json.loads(raw_text)
            msg = raw_body_data.get("message") or raw_body_data.get("error") or ""
            errs = raw_body_data.get("errors")
            if errs and isinstance(errs, dict):
                # Formatear lista de errores específicos: campo: error1, error2
                err_details = [
                    f"{field}: {', '.join(msgs) if isinstance(msgs, list) else msgs}"
                    for field, msgs in errs.items()
                ]
                detail = f"{msg} ({'; '.join(err_details)})" if msg else "; ".join(err_details)
            elif errs:
                detail = f"{msg}: {errs}" if msg else str(errs)
            else:
                detail = msg
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = ""
        invoice.status = FactusInvoice.Status.ERROR
        invoice.raw_response = raw_body_data or {"error_code": exc.code, "detail": detail}
        invoice.error_message = (
            f"Factus rechazó la factura ({exc.code})."
            + (f" Detalle: {detail}" if detail else "")
        )[:2000]
        invoice.save(update_fields=["status", "error_message", "raw_response", "updated_at"])

        # Registro centralizado de observabilidad de errores
        from DjangoProject1.apps.support.error_logging import log_system_error
        log_system_error(
            service="factus",
            level="error",
            endpoint="/v2/bills/validate",
            reference_id=f"Venta #{sale.pk}",
            error_message=f"Factus rechazó la factura (HTTP {exc.code})",
            error_details=raw_body_data.get("errors") if raw_body_data else {"raw": detail},
            request_payload=payload if "payload" in locals() else None,
            response_payload=raw_body_data,
            status_code=exc.code,
        )
        return invoice
    except (
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ):
        invoice.status = FactusInvoice.Status.ERROR
        invoice.error_message = "Factus no pudo validar la factura."
        invoice.save(update_fields=["status", "error_message", "updated_at"])
        return invoice

    data = result.get("data", {})
    links = data.get("links", {})
    invoice.number = str(data.get("number", ""))
    invoice.cufe = str(data.get("cufe", ""))
    invoice.public_url = str(links.get("public_url", ""))
    invoice.qr_url = str(links.get("qr", ""))
    invoice.raw_response = result
    if not data.get("is_validated") or not invoice.number or not invoice.cufe:
        invoice.status = FactusInvoice.Status.ERROR
        invoice.error_message = (
            "Factus no validó la factura o no devolvió número y CUFE."
        )
        invoice.save()
        return invoice
    invoice.status = FactusInvoice.Status.ISSUED
    invoice.raw_response = result
    invoice.error_message = ""
    invoice.save()
    return invoice
