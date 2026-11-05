from django.core import signing
from django.conf import settings
from django.urls import reverse

from .models import Ticket


TICKET_TOKEN_SALT = "ticket-verification"


def ticket_verification_token(ticket):
    return signing.TimestampSigner(salt=TICKET_TOKEN_SALT).sign(
        str(ticket.ticket_code)
    )


def ticket_verification_url(ticket, request):
    token = ticket_verification_token(ticket)
    path = reverse("ticket-verify")
    return request.build_absolute_uri(f"{path}?token={token}")


def get_ticket_from_verification_token(token):
    code = signing.TimestampSigner(
        salt=TICKET_TOKEN_SALT,
    ).unsign(token, max_age=settings.TICKET_VERIFICATION_MAX_AGE_SECONDS)
    return Ticket.objects.select_related(
        "trip__route__origin",
        "trip__route__destination",
        "seat",
    ).get(ticket_code=code)
