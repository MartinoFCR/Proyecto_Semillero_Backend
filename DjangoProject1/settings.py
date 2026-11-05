import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

if os.getenv("GDAL_LIBRARY_PATH"):
    os.environ["GDAL_LIBRARY_PATH"] = os.getenv("GDAL_LIBRARY_PATH")
if os.getenv("GEOS_LIBRARY_PATH"):
    os.environ["GEOS_LIBRARY_PATH"] = os.getenv("GEOS_LIBRARY_PATH")

GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH") or None
GEOS_LIBRARY_PATH = os.getenv("GEOS_LIBRARY_PATH") or None

def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]

DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not DEBUG and (
    not SECRET_KEY or SECRET_KEY == "cambia_esta_clave"
):
    raise ImproperlyConfigured(
        "SECRET_KEY debe configurarse con un valor privado en producción."
    )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")


# Application definition

INSTALLED_APPS = [
    'drf_spectacular',
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.gis',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',
    
    'DjangoProject1.apps.accounts',
    'DjangoProject1.apps.fleet',
    'DjangoProject1.apps.routes',
    'DjangoProject1.apps.trips',
    'DjangoProject1.apps.geography',
    'DjangoProject1.apps.sales',
    'DjangoProject1.apps.support',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'DjangoProject1.security_middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'DjangoProject1.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'DjangoProject1.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv("DB_NAME", "geodjango"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

AUTH_USER_MODEL = 'accounts.User'

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "DjangoProject1.apps.accounts.tokens.PasswordVersionJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "DjangoProject1.permissions.PasswordChangeRequiredPermission",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if DEBUG
            else "django.core.cache.backends.db.DatabaseCache"
        ),
        "LOCATION": os.getenv("CACHE_LOCATION", "django_cache"),
    }
}

SIMPLE_JWT = {
    # El token de acceso dura 30 minutos
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),

    # El token de renovación dura 7 días
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    # Mantener el comportamiento de renovación sencillo
    "BLACKLIST_AFTER_ROTATION": True,
    "ROTATE_REFRESH_TOKENS": True,
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
TICKET_VERIFICATION_MAX_AGE_SECONDS = int(
    os.getenv("TICKET_VERIFICATION_MAX_AGE_SECONDS", str(30 * 24 * 60 * 60))
)
LOGIN_FAILURE_LIMIT = int(os.getenv("LOGIN_FAILURE_LIMIT", "5"))
LOGIN_FAILURE_WINDOW_SECONDS = int(
    os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "900")
)

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@portalbic.site")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://portalbic.site").rstrip("/")
PASSWORD_RESET_TOKEN_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "30"))
ACCOUNT_ACTION_RATE_LIMIT = int(os.getenv("ACCOUNT_ACTION_RATE_LIMIT", "5"))
CUSTOMER_SERVICE_EMAIL = os.getenv("CUSTOMER_SERVICE_EMAIL") or None
CUSTOMER_SERVICE_PHONE = os.getenv("CUSTOMER_SERVICE_PHONE") or None
CUSTOMER_SERVICE_WHATSAPP = os.getenv("CUSTOMER_SERVICE_WHATSAPP") or None
CUSTOMER_SERVICE_HOURS = os.getenv("CUSTOMER_SERVICE_HOURS") or None
CHANGES_POLICY_URL = os.getenv("CHANGES_POLICY_URL") or None
REFUNDS_POLICY_URL = os.getenv("REFUNDS_POLICY_URL") or None
PRIVACY_POLICY_URL = os.getenv("PRIVACY_POLICY_URL") or None
TERMS_URL = os.getenv("TERMS_URL") or None

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
