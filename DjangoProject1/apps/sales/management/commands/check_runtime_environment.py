import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica la configuración de ejecución sin mostrar secretos."

    def handle(self, *args, **options):
        django_vars = (
            "SECRET_KEY",
            "ALLOWED_HOSTS",
            "FRONTEND_BASE_URL",
        )
        db_vars = (
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
            "DB_PORT",
        )
        wompi_vars = (
            "WOMPI_PUBLIC_KEY",
            "WOMPI_PRIVATE_KEY",
            "WOMPI_INTEGRITY_SECRET",
            "WOMPI_EVENTS_SECRET",
        )
        factus_vars = (
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
        email_vars = (
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "DEFAULT_FROM_EMAIL",
        )

        all_names = django_vars + db_vars + wompi_vars + factus_vars + email_vars

        result = {
            "debug": settings.DEBUG,
            "settings_module": os.environ.get("DJANGO_SETTINGS_MODULE", ""),
            "environment_summary": {
                "django": {name: bool(os.getenv(name, "").strip()) for name in django_vars},
                "database": {name: bool(os.getenv(name, "").strip()) for name in db_vars},
                "wompi": {name: bool(os.getenv(name, "").strip()) for name in wompi_vars},
                "factus": {name: bool(os.getenv(name, "").strip()) for name in factus_vars},
                "email": {name: bool(os.getenv(name, "").strip()) for name in email_vars},
            },
            "environment_flat": {
                name: bool(os.getenv(name, "").strip()) for name in all_names
            },
            "database": {
                "engine": settings.DATABASES["default"]["ENGINE"],
                "host": settings.DATABASES["default"].get("HOST", ""),
                "port": settings.DATABASES["default"].get("PORT", ""),
            },
        }
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
