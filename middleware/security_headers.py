"""Security Headers Middleware

Adds security headers to HTTP responses to protect against common web vulnerabilities.

NOTE: These headers are primarily relevant for browser-based applications.
For pure API/webhook bots, they provide minimal security benefit.

Enable these headers when:
- Adding web-based admin dashboard
- Serving HTML pages
- Implementing browser-accessible features

Disabled by default for API-only bots.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import config


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add security headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        if not config.WEBHOOK_SECURITY_HEADERS_ENABLED:
            return response

        # X-Content-Type-Options: Prevent MIME type sniffing
        # Ensures browsers respect the declared Content-Type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options: Prevent clickjacking attacks
        # Prevents the page from being loaded in a frame/iframe
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection: Enable browser XSS filter
        # Stops pages from loading when reflected XSS attacks detected
        # Note: Modern browsers rely on CSP, but this provides fallback
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict-Transport-Security: Force HTTPS connections
        # Only add if serving over HTTPS (check protocol in production)
        if config.WEBHOOK_HSTS_ENABLED:
            # max-age: 31536000 seconds = 1 year
            # includeSubDomains: Apply to all subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Referrer-Policy: Control referrer information
        # no-referrer-when-downgrade: Send referrer for same-origin and HTTPS
        response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"

        # Permissions-Policy: Control browser features
        # Disable potentially dangerous features (geolocation, camera, etc.)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        return response


class CSPMiddleware(BaseHTTPMiddleware):
    """Middleware that adds Content Security Policy headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add CSP headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with CSP headers added
        """
        response = await call_next(request)

        if not config.WEBHOOK_CSP_ENABLED:
            return response

        # Content-Security-Policy: Mitigate XSS and injection attacks
        # For a webhook/API endpoint, we have restrictive policies
        csp_directives = [
            "default-src 'none'",  # Block everything by default
            "frame-ancestors 'none'",  # Cannot be embedded in frames
            "base-uri 'none'",  # Restrict <base> tag usage
            "form-action 'none'",  # No form submissions
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response
