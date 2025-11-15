# PGP Shipping Address Encryption

## Overview

This feature enables **end-to-end encryption** of shipping addresses using PGP (Pretty Good Privacy). Customers can encrypt their shipping addresses **client-side** in a Telegram Mini App before sending them to the bot, ensuring that:

- ✅ **Zero-knowledge**: Bot cannot access plaintext addresses
- ✅ **GDPR compliant**: Meets "data minimization" principle
- ✅ **User trust**: Customers control their own data
- ✅ **Optional**: Falls back to AES-256-GCM server-side encryption

---

## Architecture

### Two Encryption Modes

1. **PGP (Client-Side)** - Recommended
   - User enters address in Telegram Mini App
   - OpenPGP.js encrypts address with public key in browser
   - Bot stores encrypted message (cannot decrypt)
   - Admin must use private key to decrypt offline

2. **AES-GCM (Server-Side)** - Fallback
   - User enters plaintext address in chat
   - Bot encrypts with AES-256-GCM using `SHIPPING_ADDRESS_SECRET`
   - Bot can decrypt for admin view

### Storage Format

**Database:** `orders` table
- `encryption_mode`: TEXT ('aes-gcm' | 'pgp')
- `encrypted_payload`: BLOB

**Binary Format:**
- **AES-GCM**: `[ciphertext][nonce 12 bytes][tag 16 bytes]`
- **PGP**: UTF-8 encoded ASCII-armored PGP message

---

## Development Setup

### Prerequisites

- GnuPG installed (`gpg` command)
- Python 3.11+
- SQLite database

### Step 1: Generate Test PGP Key

```bash
bash tools/setup_test_pgp_key.sh
```

This script:
- Generates 2048-bit RSA keypair
- Adds public key to `.env` as Base64
- Saves private key to `tools/test_pgp_private_key.asc`

### Step 2: Download OpenPGP.js

```bash
cd static/webapp
curl -o openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js
cd ../..
```

### Step 3: Configure Bot Domain

Add to `.env`:
```bash
# For local dev with ngrok
BOT_DOMAIN=https://abc123.ngrok-free.app

# For development server
BOT_DOMAIN=https://dev.yourdomain.com
```

### Step 4: Run Database Migration

```bash
# Apply SQL schema changes
sqlite3 data/database.db < migrations/014_unified_shipping_encryption.sql

# Migrate existing data (if any)
python migrations/014_unified_shipping_encryption.py
```

### Step 5: Start Bot

```bash
python run.py
```

### Step 6: Test Workflow

1. Create order with physical items
2. Choose "🔐 Sichere Verschlüsselung"
3. Mini App opens
4. Enter address
5. Click "🔐 Verschlüsseln & Senden"
6. Confirm and complete order

### Step 7: Decrypt Test Address

```bash
# Import private key (first time only)
gpg --import tools/test_pgp_private_key.asc

# Decrypt
python tools/test_decrypt_address.py <order_id>
```

---

## Production Setup

### Step 1: Generate Production PGP Key

⚠️ **CRITICAL**: Generate key on **secure offline machine**!

```bash
# Generate 4096-bit RSA key with strong passphrase
gpg --full-generate-key

# Choose:
# - RSA and RSA (default)
# - 4096 bits
# - Never expires (or set appropriate expiry)
# - Real name: "YourCompany Admin"
# - Email: admin@yourcompany.com
# - Passphrase: Use strong passphrase!
```

### Step 2: Export Public Key

```bash
# Export ASCII-armored public key
gpg --armor --export admin@yourcompany.com > public_key.asc

# Base64 encode for .env
base64 -w 0 public_key.asc > public_key_base64.txt
```

### Step 3: Configure Production Environment

Add to `.env` (or secrets manager):
```bash
# PGP public key (Base64-encoded ASCII-armored)
PGP_PUBLIC_KEY_BASE64="LS0tLS1CRUdJTiBQR1AgUFVCTElDIEtFWSBCTE9DSy0tLS0..."

# Bot domain (must be HTTPS!)
BOT_DOMAIN=bot.yourdomain.com

# Shipping address secret (for AES fallback)
SHIPPING_ADDRESS_SECRET=<generate-with-openssl-rand-base64-32>
```

### Step 4: Secure Private Key

**Option A: Hardware Security Module (HSM)**
- Best for high-security environments
- Use YubiKey or similar

**Option B: Encrypted Vault**
- Store in secure secrets manager (AWS Secrets Manager, Vault, etc.)
- Limit access to authorized personnel

**Option C: Offline Storage**
- Print QR code and store in safe
- Keep backup on encrypted USB drive

### Step 5: Deploy Bot

```bash
# Apply migration
sqlite3 /path/to/database.db < migrations/014_unified_shipping_encryption.sql
python migrations/014_unified_shipping_encryption.py

# Restart bot
docker-compose restart
```

### Step 6: Download OpenPGP.js

```bash
cd static/webapp
curl -o openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js
cd ../..
```

### Step 7: Configure Reverse Proxy

**Caddy Example:**
```caddy
bot.yourdomain.com {
    reverse_proxy localhost:8080
    tls your-email@domain.com
}
```

**Nginx Example:**
```nginx
server {
    listen 443 ssl http2;
    server_name bot.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security Best Practices

### Key Management

1. **Generate offline**: Never generate production keys on internet-connected machine
2. **Strong passphrase**: Use 20+ character passphrase with special chars
3. **Backup strategy**: Encrypted backups in multiple secure locations
4. **Access control**: Limit private key access to 2-3 authorized personnel
5. **Key rotation**: Plan for annual key rotation

### Operations

1. **Decrypt offline**: Export encrypted addresses, decrypt on air-gapped machine
2. **Audit trail**: Log all decryption operations
3. **Time-limited access**: Private key should not be permanently loaded
4. **Physical security**: Lock printed addresses in safe

### Monitoring

1. **Alert on decryption**: Notify security team when addresses are decrypted
2. **Track access**: Who, when, why for each decryption
3. **Regular audits**: Review encryption modes and key usage

---

## User Experience Flow

### For Customers (PGP Mode)

1. Create order with physical items
2. See encryption options:
   - 🔐 Secure Encryption (recommended)
   - ✍️ Manual Input
3. Click "Secure Encryption"
4. Telegram Mini App opens
5. Enter address in freitext field
6. Click "Encrypt & Send"
7. Haptic feedback + "Encrypting..." message
8. Confirmation screen shows encrypted notice
9. Continue to payment

### For Customers (Manual Mode)

1. Create order with physical items
2. Click "✍️ Manual Input"
3. Enter address as plaintext
4. Bot AES-encrypts before storing
5. Continue to payment

### For Admins

**View Encrypted Address (PGP):**
```
📬 Shipping Address:
🔐 PGP-encrypted (Admin cannot decrypt)

-----BEGIN PGP MESSAGE-----
Version: OpenPGP.js v5.11.0
Comment: https://openpgpjs.org

wcBMA1q8... [truncated]
-----END PGP MESSAGE-----
```

**View Decrypted Address (AES):**
```
📬 Shipping Address:
Max Mustermann
Musterstraße 123
12345 Musterstadt
```

---

## Troubleshooting

### "PGP public key not configured" Error

**Cause:** `PGP_PUBLIC_KEY_BASE64` not in `.env` or invalid

**Fix:**
```bash
# Check if key exists
grep PGP_PUBLIC_KEY_BASE64 .env

# If missing, add it:
echo 'PGP_PUBLIC_KEY_BASE64="..."' >> .env

# Restart bot
```

### Mini App Not Opening

**Cause:** `BOT_DOMAIN` not configured or incorrect

**Fix:**
```bash
# Check current value
grep BOT_DOMAIN .env

# Update with correct domain (HTTPS required!)
BOT_DOMAIN=https://bot.yourdomain.com

# Restart bot
```

### "openpgp.min.js not found" Error

**Cause:** OpenPGP.js not downloaded

**Fix:**
```bash
cd static/webapp
curl -o openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js
```

### Cannot Decrypt Address

**Possible causes:**
1. Wrong private key
2. Private key not in GPG keyring
3. Address encrypted with different key

**Debug:**
```bash
# List private keys
gpg --list-secret-keys

# Import private key
gpg --import tools/test_pgp_private_key.asc

# Check order encryption mode
sqlite3 data/database.db "SELECT id, encryption_mode FROM orders WHERE id = X;"
```

### Mini App Shows Blank Screen

**Causes:**
- CORS issues
- OpenPGP.js not loaded
- JavaScript errors

**Debug:**
1. Open Mini App in Telegram
2. Use Telegram's Developer Tools (if available)
3. Check browser console for errors
4. Verify OpenPGP.js loads correctly

---

## API Reference

### Configuration (`config.py`)

```python
# Required
PGP_PUBLIC_KEY_BASE64: str  # Base64-encoded ASCII-armored public key
BOT_DOMAIN: str             # Bot's public domain (HTTPS)

# Functions
load_pgp_public_key() -> str           # Load and decode public key
is_pgp_encryption_available() -> bool  # Check if PGP configured
get_webapp_url(lang: str) -> str       # Get Mini App URL
```

### Service Layer (`services/encryption_wrapper.py`)

```python
class EncryptionWrapper:
    # AES-GCM
    @staticmethod
    def encrypt_aes_gcm(plaintext: str, order_id: int) -> bytes

    @staticmethod
    def decrypt_aes_gcm(combined: bytes, order_id: int) -> str

    # PGP
    @staticmethod
    def store_pgp_encrypted(pgp_message: str) -> bytes

    @staticmethod
    def load_pgp_encrypted(encrypted_payload: bytes) -> str

    # Unified Interface
    @staticmethod
    async def save_shipping_address_unified(
        order_id: int,
        plaintext_or_pgp: str,
        encryption_mode: str,
        session: AsyncSession | Session
    )

    @staticmethod
    async def get_shipping_address_unified(
        order_id: int,
        session: AsyncSession | Session
    ) -> str | None
```

### Handlers (`handlers/user/shipping_handlers.py`)

```python
# Manual text input (AES)
@shipping_router.message(ShippingAddressStates.waiting_for_address)
async def process_shipping_address_input(...)

# Mini App WebAppData (PGP)
@shipping_router.message(F.web_app_data)
async def process_pgp_encrypted_address(...)
```

---

## Migration Guide

### From Legacy `shipping_addresses` Table

**Old Format:**
```sql
CREATE TABLE shipping_addresses (
    id INTEGER PRIMARY KEY,
    order_id INTEGER UNIQUE,
    encrypted_address BLOB,
    nonce BLOB,
    tag BLOB
);
```

**New Format:**
```sql
ALTER TABLE orders ADD COLUMN encryption_mode TEXT;
ALTER TABLE orders ADD COLUMN encrypted_payload BLOB;
```

**Migration Script:**
```bash
python migrations/014_unified_shipping_encryption.py
```

**What it does:**
1. Reads all `shipping_addresses` records
2. Combines `encrypted_address + nonce + tag` into single BLOB
3. Sets `encryption_mode = 'aes-gcm'`
4. Stores in `orders.encrypted_payload`
5. Verifies payload lengths

**After Migration:**
```bash
# Optional: Drop old table
sqlite3 data/database.db "DROP TABLE IF EXISTS shipping_addresses;"
```

---

## FAQ

### Why PGP instead of just AES?

**AES (Server-Side):**
- ✅ Simple implementation
- ✅ No user complexity
- ❌ Bot can decrypt (potential liability)
- ❌ Requires trusting server

**PGP (Client-Side):**
- ✅ Zero-knowledge architecture
- ✅ User controls their data
- ✅ GDPR "data minimization"
- ❌ More complex setup
- ❌ Admin must decrypt offline

### Can users choose encryption mode?

Yes! Users see two options:
1. **🔐 Secure Encryption** (PGP via Mini App)
2. **✍️ Manual Input** (AES by bot)

### What happens if private key is lost?

**Impact:**
- Existing PGP-encrypted addresses cannot be decrypted
- AES-encrypted addresses still work

**Prevention:**
- Keep encrypted backups in multiple locations
- Use HSM or hardware keys
- Document recovery procedures

### Is PGP encryption GDPR compliant?

Yes! PGP encryption supports:
- **Data minimization**: Bot doesn't access plaintext
- **Purpose limitation**: Only admin with private key can decrypt
- **Storage limitation**: Encrypted addresses deleted after retention period
- **Right to erasure**: User can request deletion anytime

### Performance impact?

**Minimal:**
- Client-side encryption: ~100-200ms
- OpenPGP.js: ~50KB gzipped
- No server performance impact

---

## Contributing

When contributing to PGP encryption features:

1. ✅ Test both encryption modes (PGP + AES)
2. ✅ Verify Mini App works in Telegram
3. ✅ Test decryption with `test_decrypt_address.py`
4. ✅ Update localization (de.json + en.json)
5. ✅ Add security notes to documentation

---

## License

This feature is part of AiogramShopBot.

**OpenPGP.js License:** LGPL-3.0
https://github.com/openpgpjs/openpgpjs

---

## Support

For questions or issues:
1. Check troubleshooting section
2. Review logs: `tail -f logs/bot.log`
3. Test with tools: `python tools/test_decrypt_address.py`
4. Open issue on GitHub (if applicable)

---

**Last Updated:** 2025-01-15
**Feature Version:** 1.0.0
**Migration:** 014
