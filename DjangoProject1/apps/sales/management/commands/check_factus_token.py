import json

from django.core.management.base import BaseCommand

from ...services import factus_token_diagnostics


class Command(BaseCommand):
    help = "Verifica la respuesta de autenticacion de Factus sin mostrar secretos."

    def handle(self, *args, **options):
        result = factus_token_diagnostics()
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
