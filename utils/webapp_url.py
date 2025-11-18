"""
Utility functions for generating Telegram Mini App URLs.
"""

import config
from exceptions.shipping import BotDomainNotConfiguredException
from enums.runtime_environment import RuntimeEnvironment


def _get_current_domain() -> str:
    """
    Get current domain for webapp URLs.

    In DEV mode: Dynamically fetches current ngrok URL (survives ngrok restarts)
    In PROD mode: Dynamically fetches current external IP via sslip.io (survives IP changes)
    Fallback: Uses configured BOT_DOMAIN if dynamic lookup fails

    Returns:
        str: Domain for webapp URLs (with https:// prefix)

    Raises:
        BotDomainNotConfiguredException: If domain cannot be determined
    """
    # DEV mode: Get current ngrok URL dynamically
    if config.RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
        try:
            from pyngrok import ngrok
            tunnels = ngrok.get_tunnels()

            if tunnels:
                # Get HTTPS tunnel (bind_tls=True creates HTTPS-only tunnel)
                ngrok_url = tunnels[0].public_url
                return ngrok_url
        except Exception:
            # Fall back to configured BOT_DOMAIN if ngrok not running
            pass

    # PROD mode: Get current external IP dynamically via sslip.io
    elif config.RUNTIME_ENVIRONMENT == RuntimeEnvironment.PROD:
        try:
            from external_ip import get_sslipio_external_url
            sslip_url = get_sslipio_external_url()
            return sslip_url
        except Exception:
            # Fall back to configured BOT_DOMAIN if external IP lookup fails
            pass

    # Fallback: Use configured BOT_DOMAIN
    if not config.BOT_DOMAIN:
        raise BotDomainNotConfiguredException()

    domain = config.BOT_DOMAIN
    if not domain.startswith("http://") and not domain.startswith("https://"):
        domain = f"https://{domain}"

    return domain


def get_webapp_url(endpoint: str, lang: str = "de", **query_params) -> str:
    """
    Generate full URL for Telegram Mini App endpoint.

    Args:
        endpoint: API endpoint path (e.g., "/webapp/pgp-address-input")
        lang: Language code (default: "de")
        **query_params: Additional query parameters (e.g., order_id=123)

    Returns:
        str: Full HTTPS URL for the webapp endpoint

    Examples:
        >>> get_webapp_url("/webapp/pgp-address-input", lang="de", order_id=42)
        'https://example.com/webapp/pgp-address-input?lang=de&order_id=42'

    Raises:
        BotDomainNotConfiguredException: If BOT_DOMAIN not configured
    """
    # Get domain (dynamically in DEV mode, static in PROD)
    domain = _get_current_domain()

    # Remove trailing slash from domain
    domain = domain.rstrip("/")

    # Build query string
    query_params["lang"] = lang
    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())

    return f"{domain}{endpoint}?{query_string}"