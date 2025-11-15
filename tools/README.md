# PGP Shipping Address Encryption - Testing Tools

This directory contains tools for setting up and testing PGP-encrypted shipping addresses.

## Tools

### 1. `setup_test_pgp_key.sh`

Generates a test PGP keypair for development and adds it to `.env`.

**Usage:**
```bash
bash tools/setup_test_pgp_key.sh
```

**What it does:**
- Generates a 2048-bit RSA PGP keypair
- Exports public key and Base64-encodes it
- Updates `.env` with `PGP_PUBLIC_KEY_BASE64`
- Saves private key to `tools/test_pgp_private_key.asc`
- Adds private key to `.gitignore`

**Prerequisites:**
- GnuPG installed (`gpg` command)
  - macOS: `brew install gnupg`
  - Ubuntu: `sudo apt install gnupg`
  - Arch: `sudo pacman -S gnupg`

---

### 2. `test_decrypt_address.py`

Decrypts PGP-encrypted shipping addresses from the database for testing.

**Usage:**
```bash
python tools/test_decrypt_address.py <order_id>
```

**Example:**
```bash
python tools/test_decrypt_address.py 42
```

**Prerequisites:**
1. Run `setup_test_pgp_key.sh` first
2. Import private key into GPG keyring:
   ```bash
   gpg --import tools/test_pgp_private_key.asc
   ```
3. Create an order with PGP-encrypted address via Mini App

**What it does:**
- Queries database for order
- Checks encryption mode (must be 'pgp')
- Decrypts encrypted_payload using GPG
- Displays plaintext shipping address

---

## Complete Workflow for Testing

### Step 1: Generate Test Key
```bash
bash tools/setup_test_pgp_key.sh
```

This will:
- Generate keypair
- Update `.env`
- Save private key to `tools/test_pgp_private_key.asc`

### Step 2: Download OpenPGP.js
```bash
cd static/webapp
curl -o openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js
cd ../..
```

### Step 3: Configure Bot Domain
Add to `.env`:
```bash
BOT_DOMAIN=https://your-ngrok-url.ngrok-free.app
```

Or for production:
```bash
BOT_DOMAIN=bot.yourdomain.com
```

### Step 4: Run Database Migration
```bash
python migrations/014_unified_shipping_encryption.py
```

### Step 5: Start Bot
```bash
python run.py
```

### Step 6: Test via Telegram
1. Create order with physical items
2. Click "🔐 Sichere Verschlüsselung (empfohlen)"
3. Mini App opens
4. Enter shipping address
5. Click "🔐 Verschlüsseln & Senden"
6. Confirm and complete order

### Step 7: Decrypt Address
```bash
# Import private key (first time only)
gpg --import tools/test_pgp_private_key.asc

# Decrypt address for order #42
python tools/test_decrypt_address.py 42
```

---

## Security Notes

⚠️ **IMPORTANT: Test Keys Only!**

These tools are for **development and testing only**. Do NOT use in production!

**Production Requirements:**
1. Generate key on secure offline machine
2. Use strong passphrase
3. Store private key in secure vault (not in repo!)
4. Limit private key access to authorized personnel
5. Use key management best practices
6. Consider hardware security keys (YubiKey, etc.)

**Why PGP for Shipping Addresses?**
- **Zero-knowledge**: Bot cannot access plaintext addresses
- **Compliance**: Meets GDPR "data minimization" principle
- **Trust**: Customers control their own data
- **Audit trail**: Admin can prove encryption without accessing data

---

## Troubleshooting

### "gpg: No private key" error
```bash
# List private keys
gpg --list-secret-keys

# If empty, import key:
gpg --import tools/test_pgp_private_key.asc
```

### "Order has no encrypted shipping address"
The order doesn't have a shipping address yet. Make sure:
1. Order contains physical items
2. User completed address input
3. Address was saved to database

### "Cannot decrypt with this tool (use AES decryption)"
The order uses AES-GCM encryption (manual input), not PGP.
Use `ShippingService.get_shipping_address_unified()` instead.

### Private key file missing
Run `setup_test_pgp_key.sh` again to regenerate.

---

## Files

- `setup_test_pgp_key.sh` - Key generation script
- `test_decrypt_address.py` - Decryption test script
- `test_pgp_private_key.asc` - Private key (gitignored, generated)
- `README.md` - This file
