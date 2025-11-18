import os

from pyngrok import ngrok


def start_ngrok():
    """
    Start ngrok tunnel with HTTPS only.

    Security: Always use HTTPS to encrypt webhook traffic and protect
    bot token and user data from man-in-the-middle attacks.

    Note: bind_tls=True ensures only HTTPS tunnel is created (no HTTP).
    Without it, ngrok v2 creates both HTTP and HTTPS tunnels by default.

    Ngrok Warning: Free plan shows interstitial warning page that breaks
    Telegram WebApp integration. The warning cannot be suppressed programmatically
    via pyngrok API (ngrok v2/v3 API limitation).

    Solutions:
    - Use production server with real domain (sslip.io + Let's Encrypt)
    - Upgrade to ngrok paid plan (no warning)
    - Use alternative tunnel service (cloudflared, localtunnel)

    Returns:
        str: HTTPS tunnel URL
    """
    ngrok_token = os.environ.get("NGROK_TOKEN")
    port = os.environ.get("WEBAPP_PORT")
    ngrok.set_auth_token(ngrok_token)

    # Use HTTP protocol with bind_tls=True to get HTTPS-only tunnel
    # Note: request_header cannot be set via pyngrok - requires ngrok config file
    https_tunnel = ngrok.connect(f":{port}", "http", bind_tls=True)
    return https_tunnel.public_url
