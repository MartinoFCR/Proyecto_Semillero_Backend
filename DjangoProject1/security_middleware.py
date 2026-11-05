from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = settings.SECURE_REFERRER_POLICY
        if request.is_secure() and settings.SECURE_HSTS_SECONDS:
            response["Strict-Transport-Security"] = (
                f"max-age={settings.SECURE_HSTS_SECONDS}; "
                "includeSubDomains; preload"
            )
        return response
