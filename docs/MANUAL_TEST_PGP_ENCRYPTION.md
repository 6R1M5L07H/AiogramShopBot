# Manual Test Guide: PGP Shipping Address Encryption

This guide describes how to manually test the PGP end-to-end encryption feature for shipping addresses.

## Prerequisites

1. **Test Environment**: Deploy to test server (NOT localhost - Telegram WebApp requires HTTPS)
2. **Domain**: Configured domain with valid SSL certificate
3. **PGP Keypair**: Generated using `tools/setup_pgp_keys.sh`
4. **Telegram Bot**: Test bot with webhook configured

## Setup Instructions

### 1. Generate PGP Keypair

```bash
cd /path/to/AiogramShopBot
bash tools/setup_pgp_keys.sh
```

Follow prompts:
- Enter name: "Test Admin"
- Enter email: "test@example.com"
- Passphrase: (optional, recommended for production)

Output:
- `pgp_public.asc` - Public key for encryption
- `pgp_private.asc` - Private key for decryption (**KEEP SECURE!**)

### 2. Configure Environment

Add to `.env` on test server:

```bash
# PGP Encryption
PGP_PUBLIC_KEY_BASE64="<base64_string_from_setup_script>"
BOT_DOMAIN="your-test-domain.com"

# Data Retention (for testing, use short period)
DATA_RETENTION_DAYS=30
```

### 3. Deploy to Test Server

```bash
# Sync code to test server
rsync -avz --exclude='.venv' --exclude='data/' . test-server:/path/to/bot/

# On test server: restart bot
ssh test-server
cd /path/to/bot
docker-compose restart bot
```

### 4. Verify Deployment

Check that endpoint is accessible:

```bash
curl https://your-test-domain.com/webapp/pgp-address-input?order_id=1&lang=de
```

Expected: HTML page with OpenPGP.js loaded

## Test Scenarios

### Test 1: Create Order with PGP-Encrypted Address

**Objective**: Verify that users can enter shipping addresses via encrypted Mini App.

**Steps**:

1. Start bot: `/start`
2. Navigate to catalog and add physical item to cart
3. Proceed to checkout
4. Click "🛒 Zur Kasse"
5. **Expected**: Message asking for shipping address with button "🔒 Verschlüsselt eingeben"
6. Click "🔒 Verschlüsselt eingeben" button
7. **Expected**: Telegram Mini App opens (WebView)
8. **Verify**: Mini App shows:
   - Title: "📬 Lieferadresse (verschlüsselt)"
   - Security notice about end-to-end encryption
   - Text area for address input
   - Button: "🔒 Verschlüsseln & Senden"

9. Enter test address:
   ```
   Max Mustermann
   Teststraße 123
   12345 Teststadt
   Deutschland
   ```

10. Click "🔒 Verschlüsseln & Senden"
11. **Expected**: Mini App closes, bot confirms address saved
12. Complete order by paying

**Success Criteria**:
- ✅ Mini App opens without errors
- ✅ Address is encrypted in browser (check browser console for "Encrypting address...")
- ✅ Bot receives encrypted data via web_app_data
- ✅ Order proceeds to payment screen
- ✅ No plaintext address visible in bot messages

### Test 2: Verify Database Storage

**Objective**: Confirm address is stored encrypted in database.

**Steps**:

1. After Test 1, query database:

```bash
sqlite3 data/shop.db
SELECT id, encryption_mode, length(encrypted_payload)
FROM orders
WHERE id = <order_id_from_test1>;
```

**Expected Output**:
```
123|pgp|1234
```

2. Try to view encrypted payload:

```sql
SELECT encrypted_payload FROM orders WHERE id = <order_id>;
```

**Expected**: Binary blob starting with `-----BEGIN PGP MESSAGE-----`

**Success Criteria**:
- ✅ `encryption_mode` = "pgp"
- ✅ `encrypted_payload` is populated (not NULL)
- ✅ Payload is PGP-armored message (starts with `-----BEGIN PGP MESSAGE-----`)
- ✅ No plaintext address in database

### Test 3: Admin Decryption (Offline with Standard GPG Tools)

**Objective**: Verify authorized admins can decrypt addresses using standard GPG tools.

**Steps**:

1. Query encrypted address from database:

```bash
sqlite3 data/shop.db "SELECT encrypted_payload FROM orders WHERE id = <order_id_from_test1>;" > encrypted_message.txt
```

2. Decrypt using standard GPG command line:

```bash
# Import private key (if not already imported)
gpg --import pgp_private.asc

# Decrypt the message
cat encrypted_message.txt | gpg --decrypt
```

**Alternative with Kleopatra (GUI)**:
1. Export encrypted message to file
2. Open Kleopatra
3. File → Decrypt/Verify
4. Select encrypted message file
5. Enter passphrase if prompted

**Expected Output**:
```
gpg: encrypted with 4096-bit RSA key, ID XXXXXXXX, created 2025-11-16
      "Shop Bot Admin <admin@example.com>"
Max Mustermann
Teststraße 123
12345 Teststadt
Deutschland
```

**Success Criteria**:
- ✅ Standard GPG tools can decrypt messages
- ✅ No custom code required for decryption
- ✅ Output matches original address from Test 1
- ✅ Works with passphrase-protected keys

### Test 4: AES-GCM Fallback Mode

**Objective**: Verify server-side AES-GCM encryption for manual input.

**Steps**:

1. Create new order (same as Test 1 steps 1-4)
2. Instead of clicking "🔒 Verschlüsselt eingeben", send address as plaintext message:
   ```
   Anna Schmidt
   Hauptstraße 456
   54321 Musterort
   Österreich
   ```

3. Confirm address
4. Complete order

5. Query database:

```sql
SELECT encryption_mode, length(encrypted_payload)
FROM orders
WHERE id = <order_id_from_test4>;
```

**Expected**: `aes-gcm|<some_length>`

6. Note: AES-GCM decryption requires the bot's SHIPPING_ADDRESS_SECRET (from .env)

**Expected**:
- Address is encrypted in database
- Only bot can decrypt (has secret key)
- This is server-side encryption (bot has access)

**Success Criteria**:
- ✅ Plaintext input still works (backward compatibility)
- ✅ Address is encrypted with AES-GCM (not stored plaintext)
- ✅ PGP mode is stronger (bot cannot decrypt PGP, only AES-GCM)

### Test 5: Admin Order Management View

**Objective**: Verify admins can view orders with encrypted addresses.

**Steps**:

1. As admin, navigate to: "📦 Auftragsverwaltung"
2. Select order from Test 1 or Test 4
3. **Expected**: Order details show:
   - "📬 **Versandadresse:**"
   - "🔒 Verschlüsselt (wird nach 30 Tagen gelöscht)"
   - **NO plaintext address visible**

4. Mark order as shipped
5. Verify customer receives notification

**Success Criteria**:
- ✅ Admin panel does NOT show plaintext addresses
- ✅ Encryption status is clearly indicated
- ✅ Order workflow (mark shipped, cancel) works normally
- ✅ No errors in admin interface

### Test 6: Data Retention (Extended Test)

**Objective**: Verify addresses are deleted after retention period.

**Note**: This test requires waiting DATA_RETENTION_DAYS (default: 30 days). For testing, temporarily set `DATA_RETENTION_DAYS=1` in config and run data retention job.

**Steps**:

1. Create order with encrypted address (Test 1)
2. Set `DATA_RETENTION_DAYS=1` in .env
3. Run retention job:

```bash
python jobs/data_retention_cleanup_job.py --dry-run=false
```

4. Query database:

```sql
SELECT encryption_mode, encrypted_payload
FROM orders
WHERE id = <order_id>;
```

**Expected**: Both fields are NULL

**Success Criteria**:
- ✅ Encrypted addresses are deleted after retention period
- ✅ Order record remains (only address deleted, not order)
- ✅ Cleanup job logs deletion

### Test 7: Error Handling

**Objective**: Verify graceful error handling.

**Test 7a: PGP Key Not Configured**

1. Remove `PGP_PUBLIC_KEY_BASE64` from .env
2. Restart bot
3. Try to create order with physical items
4. **Expected**: Only plaintext input available (no encrypted button)

**Test 7b: BOT_DOMAIN Not Configured**

1. Remove `BOT_DOMAIN` from .env
2. Restart bot
3. Try to create order
4. **Expected**: Same as 7a - no encrypted button shown

**Test 7c: Invalid PGP Message**

1. Manually insert corrupted encrypted_payload:

```sql
UPDATE orders
SET encryption_mode='pgp', encrypted_payload='invalid-data'
WHERE id=<test_order_id>;
```

2. Try to decrypt with GPG:

```bash
sqlite3 data/shop.db "SELECT encrypted_payload FROM orders WHERE id = <test_order_id>;" | gpg --decrypt
```

**Expected**: GPG error message "gpg: decrypt failed: ..."

**Test 7d: WebApp Connection Failure**

1. Temporarily stop bot/nginx
2. Try to open Mini App
3. **Expected**: Telegram shows connection error (not bot crash)

**Success Criteria**:
- ✅ Missing config gracefully falls back to plaintext mode
- ✅ GPG shows helpful error messages for corrupted data
- ✅ No exceptions crash the bot
- ✅ Users see appropriate error messages

## Test 8: Localization

**Objective**: Verify Mini App works in both German and English.

**Steps**:

1. Set Telegram language to German
2. Create order → open Mini App
3. **Verify**: All text in German ("Lieferadresse", "Verschlüsseln & Senden")

4. Set Telegram language to English
5. Create new order → open Mini App
6. **Verify**: All text in English ("Shipping Address", "Encrypt & Send")

**Success Criteria**:
- ✅ Mini App detects user language from Telegram
- ✅ All UI text is localized correctly
- ✅ Error messages are localized

## Security Checklist

Before deploying to production, verify:

- [ ] PGP private key is NOT in git repository
- [ ] PGP private key is stored securely (password manager, vault)
- [ ] Private key has strong passphrase
- [ ] Only authorized admins have access to private key
- [ ] BOT_DOMAIN uses HTTPS (not HTTP)
- [ ] SSL certificate is valid
- [ ] Webhook uses HTTPS
- [ ] Data retention period is configured (default: 30 days)
- [ ] Cleanup job is scheduled (cron/systemd timer)
- [ ] Admin decryption is logged for audit
- [ ] No hardcoded secrets in code

## Troubleshooting

### Mini App doesn't open

- Check BOT_DOMAIN is set correctly in .env
- Verify domain is accessible via HTTPS
- Check bot logs for errors
- Test endpoint manually: `curl https://yourdomain.com/webapp/pgp-address-input?order_id=1&lang=de`

### Decryption fails

- Verify private key is imported in GPG: `gpg --list-secret-keys`
- Check passphrase is correct
- Try decrypting standalone message to test key: `echo "test" | gpg --encrypt -r "admin@example.com" | gpg --decrypt`
- Use Kleopatra (GUI) for easier key management

### Address not saved

- Check bot logs for errors
- Verify web_app_data handler is registered
- Test JSON format: Mini App should send `{"order_id": 123, "encrypted_address": "...", "encryption_mode": "pgp"}`

### Database errors

- Verify migration 014 was applied: `SELECT name FROM sqlite_master WHERE type='table' AND name='orders';`
- Check columns exist: `PRAGMA table_info(orders);`
- Should see: `encryption_mode TEXT` and `encrypted_payload BLOB`

## Success Criteria Summary

All tests pass when:

- ✅ Mini App opens and encrypts addresses in browser
- ✅ PGP-encrypted addresses stored in database (not plaintext)
- ✅ AES-GCM fallback works for manual input
- ✅ Standard GPG tools successfully decrypt PGP addresses
- ✅ Admin panel hides plaintext addresses
- ✅ Data retention deletes addresses after configured period
- ✅ Error handling is graceful (no crashes)
- ✅ Localization works for de/en
- ✅ Security checklist items verified
- ✅ No sensitive data in git repository

## Reporting Issues

If tests fail, collect:

1. Bot logs (last 100 lines)
2. Browser console logs (from Mini App)
3. Database schema: `sqlite3 data/shop.db ".schema orders"`
4. Config (redacted): `grep PGP .env | sed 's/=.*/=***/'`
5. Error messages (full traceback)

Submit to: [Issue Tracker / Developer Contact]
