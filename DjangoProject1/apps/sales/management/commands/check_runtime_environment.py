import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica la configuración de ejecución sin mostrar secretos."

    def handle(self, *args, **options):
        names = (
            "SECRET_KEY",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
            "DB_PORT",
            "FACTUS_BASE_URL",
            "FACTUS_USERNAME",
            "FACTUS_PASSWORD",
            "FACTUS_CLIENT_ID",
            "FACTUS_CLIENT_SECRET",
            "FACTUS_NUMBERING_RANGE_ID",
            "FACTUS_PRODUCT_CODE",
            "FACTUS_PRODUCT_NAME",
            "FACTUS_MUNICIPALITY_CODE",
            "FACTUS_UNIT_MEASURE_CODE",
            "FACTUS_STANDARD_CODE",
            "FACTUS_TAX_CODE",
            "FACTUS_TAX_RATE",
            "FACTUS_TAX_EXCLUDED",
        )
        result = {
            "debug": settings.DEBUG,
            "settings_module": os.environ.get(
                "DJANGO_SETTINGS_MODULE", ""
            ),
            "environment": {
                name: bool(os.getenv(name, "").strip()) for name in names
            },
            "database": {
                "engine": settings.DATABASES["default"]["ENGINE"],
                "host": settings.DATABASES["default"].get("HOST", ""),
                "port": settings.DATABASES["default"].get("PORT", ""),
            },
        }
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
