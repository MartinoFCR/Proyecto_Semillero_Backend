import json
from urllib.error import HTTPError, URLError

from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from ...services import factus_invoice_diagnostics


class Command(BaseCommand):
    help = "Envía el payload de prueba de Factus y muestra su respuesta."

    def handle(self, *args, **options):
        try:
            result = factus_invoice_diagnostics()
        except (
            HTTPError,
            URLError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
            ValidationError,
            ValueError,
        ) as exc:
            raise CommandError(
                f"No fue posible ejecutar la prueba de Factus: {exc}"
            ) from exc
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
