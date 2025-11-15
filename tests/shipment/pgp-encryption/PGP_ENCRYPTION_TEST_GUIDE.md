# PGP Shipping Address Encryption - Test Guide

**Feature:** Client-side PGP encryption for shipping addresses
**Date:** 2025-01-15
**Migration:** 014_unified_shipping_encryption
**Related Docs:** `/docs/PGP_SHIPPING_ENCRYPTION.md`, `/tools/README.md`

---

## Overview

This test guide covers the PGP shipping address encryption feature, which allows customers to encrypt their shipping addresses **client-side** before sending them to the bot.

**Two Encryption Modes:**
1. **PGP (Client-Side)** - Via Telegram Mini App with OpenPGP.js
2. **AES-GCM (Server-Side)** - Manual plaintext input, bot encrypts

---

## Prerequisites

### 1. Environment Setup

```bash
# Generate test PGP key
bash tools/setup_test_pgp_key.sh

# Download OpenPGP.js
curl -o static/webapp/openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js

# Configure bot domain in .env
echo 'BOT_DOMAIN=https://your-ngrok-url.ngrok-free.app' >> .env
```

### 2. Database Migration

```bash
# Apply schema changes
sqlite3 data/database.db < migrations/014_unified_shipping_encryption.sql

# Migrate existing data (if any)
python migrations/014_unified_shipping_encryption.py
```

### 3. Import Private Key (for decryption tests)

```bash
gpg --import tools/test_pgp_private_key.asc
```

### 4. Start Bot

```bash
python run.py
```

---

## Test Cases

### TC-PGP-001: Mini App Opens Correctly

**Preconditions:**
- Bot running with PGP key configured
- OpenPGP.js downloaded
- BOT_DOMAIN configured

**Steps:**
1. Create order with physical items
2. Add items to cart
3. Proceed to checkout
4. Click "🛍️ Kasse"

**Expected Result:**
- Order creation screen shows two buttons:
  - ✅ "🔐 Sichere Verschlüsselung (empfohlen)"
  - ✅ "✍️ Manuell eingeben"

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-002: Mini App Encryption Flow

**Steps:**
1. Click "🔐 Sichere Verschlüsselung"
2. Mini App opens in Telegram WebView
3. Enter test address:
   ```
   Max Mustermann
   Teststraße 123
   12345 Teststadt
   ```
4. Click "🔐 Verschlüsseln & Senden"

**Expected Result:**
- ✅ Haptic feedback (vibration)
- ✅ "Verschlüssele..." message
- ✅ Success message: "Verschlüsselt! Sende an Bot..."
- ✅ Mini App closes automatically
- ✅ Confirmation screen in chat:
  ```
  ✅ Adresse verschlüsselt erhalten!

  🔐 Ihre Versandadresse wurde mit PGP-Verschlüsselung gesichert...

  Möchten Sie fortfahren?
  [✅ Bestätigen] [✏️ Adresse ändern]
  ```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-003: Manual Input Flow (AES Fallback)

**Steps:**
1. Create order with physical items
2. Click "✍️ Manuell eingeben"
3. Enter plaintext address in chat
4. Bot shows confirmation

**Expected Result:**
- ✅ Bot stores address with `encryption_mode='aes-gcm'`
- ✅ Confirmation message shows plaintext preview
- ✅ Database: `orders.encrypted_payload` contains AES-encrypted data

**Verification:**
```bash
sqlite3 data/database.db "SELECT id, encryption_mode, length(encrypted_payload) FROM orders WHERE id = X;"
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-004: PGP Decryption (Admin)

**Steps:**
1. Complete order with PGP-encrypted address (TC-PGP-002)
2. Get order ID from database
3. Run decryption script:
   ```bash
   python tools/test_decrypt_address.py <order_id>
   ```

**Expected Result:**
```
============================================================
PGP Shipping Address Decryption Test
============================================================

🔍 Looking up order #42...

✅ Order found
   Encryption mode: pgp
   Payload size: 856 bytes

🔐 Decrypting...

============================================================
✅ Decryption Successful!
============================================================

📬 Shipping Address:
────────────────────────────────────────────────────────────
Max Mustermann
Teststraße 123
12345 Teststadt
────────────────────────────────────────────────────────────

🔑 Decryption Info:
   Key ID: ABCD1234EFGH5678
   Username: Test Bot Admin <admin@testbot.local>
   Fingerprint: ...
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-005: Admin View Shows Encrypted Address

**Steps:**
1. Complete order with PGP-encrypted address
2. Navigate to Admin → Auftragsverwaltung
3. Open order details

**Expected Result (PGP Mode):**
```
📦 Bestelldetails #INV-2025-001

Kunde: @testuser (ID: 123456)

📬 Lieferadresse:
🔐 PGP-verschlüsselt (Admin kann nicht entschlüsseln)

-----BEGIN PGP MESSAGE-----
Version: OpenPGP.js v5.11.0
Comment: https://openpgpjs.org

wcBMA1q8... [truncated]
-----END PGP MESSAGE-----
```

**Expected Result (AES Mode):**
```
📬 Lieferadresse:
Max Mustermann
Teststraße 123
12345 Teststadt
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-006: User View Shows Encrypted Notice

**Steps:**
1. As user, view own order history
2. Open order with shipping address

**Expected Result:**
- ✅ User sees encrypted notice, NOT the plaintext address:
  ```
  📬 Lieferadresse:
  🔒 Verschlüsselt (wird nach 30 Tagen gelöscht)
  ```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-007: Re-enter Address Flow

**Steps:**
1. Complete encryption (TC-PGP-002)
2. On confirmation screen, click "✏️ Adresse ändern"
3. Mini App opens again
4. Enter different address
5. Encrypt & send

**Expected Result:**
- ✅ New address replaces old one
- ✅ New confirmation screen appears
- ✅ Database updated with new encrypted_payload

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-008: Cancel Order Flow

**Steps:**
1. Start encryption flow
2. Click "❌ Abbrechen" in Mini App or chat

**Expected Result:**
- ✅ Mini App closes
- ✅ Order remains in PENDING_PAYMENT_AND_ADDRESS state
- ✅ User can restart address input or cancel order

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-009: Missing PGP Key Fallback

**Steps:**
1. Remove PGP_PUBLIC_KEY_BASE64 from .env
2. Restart bot
3. Create order with physical items

**Expected Result:**
- ✅ Only "✍️ Manuell eingeben" button shown
- ✅ No Mini App option (PGP not available)
- ✅ User can still complete order with AES encryption

**Verification:**
```python
from services.shipping import ShippingService
print(ShippingService.is_pgp_available())  # Should be False
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-010: Data Retention Cleanup

**Steps:**
1. Create order with shipping address
2. Set retention period to 1 day (for testing)
3. Manually advance system time or wait
4. Run cleanup job:
   ```bash
   python jobs/data_retention_cleanup_job.py
   ```

**Expected Result:**
- ✅ `orders.encrypted_payload` set to NULL
- ✅ `orders.encryption_mode` set to NULL
- ✅ Order status unchanged

**Verification:**
```bash
sqlite3 data/database.db "SELECT id, encrypted_payload, encryption_mode FROM orders WHERE id = X;"
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-011: Migration from Legacy Table

**Preconditions:**
- Existing `shipping_addresses` table with data

**Steps:**
1. Run migration script:
   ```bash
   python migrations/014_unified_shipping_encryption.py
   ```
2. Check verification output

**Expected Result:**
```
==========================================
Migration: Unified Shipping Encryption
==========================================

Starting shipping address migration...
✅ Successfully migrated 42 shipping addresses to unified storage
   Old table: shipping_addresses (3 columns)
   New storage: orders.encrypted_payload (1 BLOB + mode)

Verifying migration...
✅ Found 42 orders with encryption_mode='aes-gcm'
✅ Migration verification successful

==========================================
✅ Migration completed successfully!
==========================================

Next steps:
1. Test decryption with ShippingService.get_shipping_address_unified()
2. After verification, drop old table:
   sqlite3 data/database.db 'DROP TABLE IF EXISTS shipping_addresses;'
```

**Verification:**
```bash
# Check migrated data
sqlite3 data/database.db "
SELECT
  id,
  encryption_mode,
  length(encrypted_payload) as payload_size
FROM orders
WHERE encryption_mode = 'aes-gcm'
LIMIT 5;
"
```

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

### TC-PGP-012: Localization (German + English)

**Steps:**
1. Test with `BOT_LANGUAGE=de` in .env
2. Restart bot
3. Complete encryption flow
4. Switch to `BOT_LANGUAGE=en`
5. Restart and test again

**Expected Result:**

**German (`de`):**
- "🔐 Sichere Verschlüsselung (empfohlen)"
- "✍️ Manuell eingeben"
- Mini App header: "🔐 Sichere Versandadresse"
- Button: "🔐 Verschlüsseln & Senden"

**English (`en`):**
- "🔐 Secure Encryption (recommended)"
- "✍️ Enter Manually"
- Mini App header: "🔐 Secure Shipping Address"
- Button: "🔐 Encrypt & Send"

**Actual Result:** ___________
**Status:** ⬜ PASS ⬜ FAIL

---

## Edge Cases

### EDGE-001: Invalid PGP Key in .env

**Setup:**
```bash
# Add invalid Base64 to .env
echo 'PGP_PUBLIC_KEY_BASE64="INVALID_BASE64!!!"' >> .env
```

**Expected:**
- Bot logs error at startup
- `is_pgp_encryption_available()` returns False
- Only manual input available

---

### EDGE-002: OpenPGP.js Failed to Load

**Simulation:**
- Remove `static/webapp/openpgp.min.js`
- Open Mini App

**Expected:**
- JavaScript error in console
- Encryption fails gracefully
- User can click "❌ Abbrechen" and use manual input

---

### EDGE-003: Very Long Address (>2000 chars)

**Test:**
- Enter 3000-character address in Mini App

**Expected:**
- Encryption succeeds
- Storage works (BLOB has no practical limit)
- Decryption succeeds

---

### EDGE-004: Special Characters in Address

**Test Address:**
```
Müller & Söhne GmbH
Straße der Freiheit 42
Österreich-Platz 7/13
80331 München
Deutschland 🇩🇪
```

**Expected:**
- UTF-8 encoding preserved
- Encryption/decryption correct
- Admin view displays correctly

---

## Performance Tests

### PERF-001: Encryption Speed

**Method:**
- Measure time from button click to completion
- Use browser developer tools

**Acceptance Criteria:**
- < 500ms for encryption (client-side)
- < 100ms for storage (server-side)

---

### PERF-002: Mini App Load Time

**Method:**
- Measure WebView load time
- Include OpenPGP.js download

**Acceptance Criteria:**
- < 2 seconds on 3G connection
- < 1 second on WiFi

---

## Security Tests

### SEC-001: Bot Cannot Decrypt PGP Addresses

**Verification:**
```python
# Try to decrypt PGP payload with bot code
from services.encryption_wrapper import EncryptionWrapper
from db import get_db_session
from models.order import Order

async with get_db_session() as session:
    order = await session.get(Order, order_id)
    if order.encryption_mode == "pgp":
        # This should return the PGP message, NOT plaintext
        address = await EncryptionWrapper.get_shipping_address_unified(order_id, session)
        assert address.startswith("-----BEGIN PGP MESSAGE-----")
```

---

### SEC-002: AES Key Derivation

**Verification:**
- Each order uses unique key (order_id in salt)
- PBKDF2 with 100,000 iterations
- SHA256 hash

**Code Review:** `services/encryption_wrapper.py:_derive_aes_key()`

---

### SEC-003: No Plaintext Leaks in Logs

**Method:**
1. Set `LOG_LEVEL=DEBUG` in .env
2. Complete order with address
3. Check logs

**Expected:**
- ✅ No plaintext addresses in logs
- ✅ Only encrypted payloads or "[ENCRYPTED]" markers

---

## Manual Test Checklist

### Setup (One-Time)
- ⬜ Generate test PGP key: `bash tools/setup_test_pgp_key.sh`
- ⬜ Download OpenPGP.js
- ⬜ Configure BOT_DOMAIN in .env
- ⬜ Run migration
- ⬜ Import private key to GPG

### For Each Test Run
- ⬜ Start fresh bot instance
- ⬜ Clear cart
- ⬜ Delete test orders from database
- ⬜ Test both encryption modes (PGP + AES)
- ⬜ Test both languages (de + en)
- ⬜ Verify admin view
- ⬜ Verify user view
- ⬜ Test decryption script

---

## Test Results Summary

| Test Case | Status | Notes | Tester | Date |
|-----------|--------|-------|--------|------|
| TC-PGP-001 | ⬜ | | | |
| TC-PGP-002 | ⬜ | | | |
| TC-PGP-003 | ⬜ | | | |
| TC-PGP-004 | ⬜ | | | |
| TC-PGP-005 | ⬜ | | | |
| TC-PGP-006 | ⬜ | | | |
| TC-PGP-007 | ⬜ | | | |
| TC-PGP-008 | ⬜ | | | |
| TC-PGP-009 | ⬜ | | | |
| TC-PGP-010 | ⬜ | | | |
| TC-PGP-011 | ⬜ | | | |
| TC-PGP-012 | ⬜ | | | |

---

## Known Issues

_(Document any issues discovered during testing)_

---

## Test Environment

- **Bot Version:** _________
- **Python Version:** _________
- **Operating System:** _________
- **Telegram Client:** _________
- **Date Tested:** _________
- **Tester:** _________

---

## References

- Feature Documentation: `/docs/PGP_SHIPPING_ENCRYPTION.md`
- Tools Documentation: `/tools/README.md`
- Migration: `/migrations/014_unified_shipping_encryption.py`
- Service Layer: `/services/encryption_wrapper.py`
