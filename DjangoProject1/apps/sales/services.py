import hashlib
import hmac
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import FactusInvoice, Payment, Purchase, Sale, Ticket


def create_ticket_for_sale(sale, trip, seat, passenger):
    if seat.bus_id != trip.bus_id:
        raise ValidationError({"seat": "La silla no pertenece al bus del viaje."})

    if Ticket.objects.filter(
        trip=trip,
        seat=seat,
        status=Ticket.Status.ISSUED,
    ).exists():
        raise ValidationError({"seat": "La silla ya está vendida para este viaje."})

    return Ticket.objects.create(
        sale=sale,
        trip=trip,
        seat=seat,
        passenger_identification=passenger["identification_number"],
        passenger_name=passenger["name"],
        passenger_email=passenger["email"],
        passenger_telephone=passenger.get("telephone", ""),
    )


def mark_sale_paid(sale, payment_status, provider_reference, raw_response):
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        if sale.status == Sale.Status.PAID:
            return sale
        if (
            sale.status == Sale.Status.PENDING
            and sale.expires_at
            and sale.expires_at <= timezone.now()
        ):
            sale.status = Sale.Status.EXPIRED
            sale.save(update_fields=["status", "updated_at"])
            return sale
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
            sale.status = Sale.Status.FAILED
            sale.save(update_fields=["status", "updated_at"])
            return sale

        sale.status = Sale.Status.PAID
        sale.save(update_fields=["status", "updated_at"])
        create_ticket_for_sale(
            sale,
            sale.trip,
            sale.seat,
            {
                "identification_number": sale.passenger_identification,
                "name": sale.passenger_name,
                "email": sale.passenger_email,
                "telephone": sale.passenger_telephone,
            },
        )
        transaction.on_commit(
            lambda sale_id=sale.pk: issue_factus_invoice(sale_id)
        )
        return sale


def mark_purchase_paid(purchase, payment_status, raw_response):
    with transaction.atomic():
        purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
        if purchase.status == Sale.Status.PAID:
            return purchase
        if purchase.status == Sale.Status.PENDING and not purchase.has_active_hold():
            purchase.status = Sale.Status.EXPIRED
            purchase.save(update_fields=["status", "updated_at"])
            return purchase
        payment, _ = Payment.objects.select_for_update().get_or_create(
            purchase=purchase,
            defaults={
                "amount_cents": purchase.amount_cents,
                "provider": "wompi",
            },
        )
        payment.status = payment_status
        payment.raw_response = raw_response
        payment.processed_at = timezone.now()
        payment.save(update_fields=["status", "raw_response", "processed_at"])
        if payment_status != "APPROVED":
            purchase.status = Sale.Status.FAILED
            purchase.save(update_fields=["status", "updated_at"])
            return purchase
        purchase.status = Sale.Status.PAID
        purchase.save(update_fields=["status", "updated_at"])
        for sale in purchase.sales.select_related("trip", "seat").all():
            create_ticket_for_sale(
                sale,
                sale.trip,
                sale.seat,
                {
                    "identification_number": sale.passenger_identification,
                    "name": sale.passenger_name,
                    "email": sale.passenger_email,
                    "telephone": sale.passenger_telephone,
                },
            )
            sale.status = Sale.Status.PAID
            sale.save(update_fields=["status", "updated_at"])
            transaction.on_commit(
                lambda sale_id=sale.pk: issue_factus_invoice(sale_id)
            )
        return purchase


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


def wompi_integrity_signature(reference, amount_cents, currency="COP"):
    secret = os.getenv("WOMPI_INTEGRITY_SECRET")
    if not secret:
        raise ValidationError("WOMPI_INTEGRITY_SECRET no está configurado.")
    payload = f"{reference}{amount_cents}{currency}{secret}"
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


def _factus_invoice_payload(sale, config):
    price = sale.amount_cents / 100
    payment_methods = {
        Sale.PaymentMethod.CASH: "10",
        Sale.PaymentMethod.TRANSFER: "47",
        Sale.PaymentMethod.CARD: "48",
        Sale.PaymentMethod.WOMPI: "48",
    }
    payload = {
        "reference_code": f"SALE-{sale.pk}",
        "document": "01",
        "operation_type": "10",
        "send_email": False,
        "observation": f"Transporte - tiquete {sale.tickets.first().ticket_code}",
        "payment_details": [
            {
                "payment_form": "1",
                "payment_method_code": payment_methods[sale.payment_method],
                "reference_code": f"SALE-{sale.pk}",
                "amount": f"{price:.2f}",
            }
        ],
        "customer": {
            "identification_document_code": "13",
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
                "name": config["FACTUS_PRODUCT_NAME"],
                "quantity": "1",
                "discount_rate": "0.00",
                "price": f"{price:.2f}",
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
        ],
    }
    if config["FACTUS_MUNICIPALITY_CODE"]:
        payload["customer"]["municipality_code"] = (
            config["FACTUS_MUNICIPALITY_CODE"]
        )
    if config["FACTUS_NUMBERING_RANGE_ID"]:
        payload["numbering_range_id"] = config["FACTUS_NUMBERING_RANGE_ID"]
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
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
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
