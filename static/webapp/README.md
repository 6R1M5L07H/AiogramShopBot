# Telegram Mini App - Shipping Address Encryption

This directory contains the static files for the PGP shipping address encryption Mini App.

## Setup: Download OpenPGP.js

The Mini App requires OpenPGP.js v5 for client-side encryption.

### Option 1: Direct Download (Recommended for Production)

```bash
cd static/webapp
curl -o openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js
```

### Option 2: Use CDN (Development Only)

For development, you can use the CDN version by editing `shipping-encrypt-template.html`:

```html
<script src="https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js"></script>
```

**⚠️ Warning:** CDN approach requires internet connection and may fail if CDN is down. Self-hosted is recommended for production.

## Files

- **shipping-encrypt-template.html** - HTML template with `{{placeholders}}` for backend rendering
- **encrypt.js** - Client-side encryption logic and Telegram WebApp API integration
- **webapp.css** - Telegram-themed styling with dark mode support
- **openpgp.min.js** - OpenPGP.js library (not included, download separately)

## How It Works

1. Backend renders template with localized strings and PGP public key
2. User enters shipping address in freitext textarea
3. Client-side JavaScript encrypts address with OpenPGP.js
4. Encrypted PGP message sent back to bot via `Telegram.WebApp.sendData()`
5. Bot stores encrypted address in `orders.encrypted_payload` with `encryption_mode='pgp'`

## Theme Support

The Mini App automatically applies Telegram's theme colors using the WebApp API:
- Light theme (default)
- Dark theme (automatic based on user's Telegram settings)

## Testing Locally

1. Ensure BOT_DOMAIN is set in .env: `BOT_DOMAIN=https://your-ngrok-url.ngrok-free.app`
2. Download OpenPGP.js: `curl -o static/webapp/openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js`
3. Run bot: `python run.py`
4. In Telegram, trigger shipping address flow and click "Encrypt Address" button
5. Mini App should open in Telegram's WebView

## Production Deployment

See main project README for Docker deployment with Caddy reverse proxy.
