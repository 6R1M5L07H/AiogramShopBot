import os

from pyngrok import ngrok


def start_ngrok():
    """
    Start ngrok tunnel with HTTPS only.

    Security: Always use HTTPS to encrypt webhook traffic and protect
    bot token and user data from man-in-the-middle attacks.

    Note: bind_tls=True ensures only HTTPS tunnel is created (no HTTP).
    Without it, ngrok v2 creates both HTTP and HTTPS tunnels by default.

    Returns:
        str: HTTPS tunnel URL
    """
    ngrok_token = os.environ.get("NGROK_TOKEN")
    port = os.environ.get("WEBAPP_PORT")
    ngrok.set_auth_token(ngrok_token)

    # Use HTTP protocol with bind_tls=True to get HTTPS-only tunnel
    # This is the correct way per pyngrok documentation
    https_tunnel = ngrok.connect(f":{port}", "http", bind_tls=True)
    return https_tunnel.public_url
