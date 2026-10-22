import hashlib
import hmac
import os
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Payment, Sale, Ticket


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
                Sale.Status.FAILED
            )
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
        return sale


def get_wompi_transaction(transaction_id):
    base_url = os.getenv("WOMPI_BASE_URL", "https://sandbox.wompi.co/v1").rstrip("/")
    private_key = os.getenv("WOMPI_PRIVATE_KEY")
    if not private_key:
        raise ValidationError("WOMPI_PRIVATE_KEY no está configurada.")

    request = Request(
        f"{base_url}/transactions/{transaction_id}",
        headers={
            "Authorization": f"Bearer {private_key}",
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
    event = payload.get("event", {})
    data = payload.get("data", {})
    signature = data.get("signature", {})
    timestamp = payload.get("timestamp")
    properties = signature.get("properties", [])
    transaction = data.get("transaction", {})
    values = "".join(str(transaction.get(prop, "")) for prop in properties)
    expected = hashlib.sha256(f"{values}{timestamp}{os.getenv('WOMPI_EVENTS_SECRET', '')}".encode()).hexdigest()
    return bool(
        signature.get("checksum")
        and hmac.compare_digest(signature["checksum"], expected)
        and event == "transaction.updated"
    )
