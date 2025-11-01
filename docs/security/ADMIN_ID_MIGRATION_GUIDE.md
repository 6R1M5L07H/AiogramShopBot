# Admin ID Hash Migration Guide

## Overview

Admin authentication has been upgraded to use SHA256 hashes instead of plaintext Telegram IDs for improved security.

**Security Benefit:** If an attacker gains access to your `.env` file, they cannot identify which Telegram accounts have admin privileges.

---

## Migration Steps

### Step 1: Generate Hashes for Your Admin IDs

Use the provided utility script to generate hashes:

```bash
python -m utils.admin_hash_generator <telegram_id>
```

**Example:**
```bash
$ python -m utils.admin_hash_generator 123456789

Telegram ID: 123456789
SHA256 Hash: 15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225

Add this hash to your .env file:
ADMIN_ID_HASHES=15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225

For multiple admins, separate with commas:
ADMIN_ID_HASHES=15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225,<hash2>,<hash3>
```

### Step 2: Update Your `.env` File

**Old (deprecated):**
```env
ADMIN_ID_LIST=123456789,987654321
```

**New (secure):**
```env
ADMIN_ID_HASHES=15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225,a4e624d686e03ed2767c0abd85c14426b0b1157d2ce81d27bb4fe4f6f01d688a
```

### Step 3: Test Your Configuration

1. Restart the bot
2. Try accessing admin features
3. Verify you can see the admin menu

If you see a security warning in logs, the bot is falling back to `ADMIN_ID_LIST` (deprecated).

### Step 4: Remove Legacy Configuration

Once you've confirmed everything works with `ADMIN_ID_HASHES`, you can remove the old variable:

```env
# Remove this line (or comment it out):
# ADMIN_ID_LIST=123456789,987654321
```

---

## Backward Compatibility

The system automatically falls back to `ADMIN_ID_LIST` if `ADMIN_ID_HASHES` is not configured.

**Warning:** Using `ADMIN_ID_LIST` will log a security warning:
```
⚠️ SECURITY WARNING: Using plaintext ADMIN_ID_LIST is deprecated.
Use ADMIN_ID_HASHES instead. Generate hashes with:
python -m utils.admin_hash_generator <telegram_id>
```

**Support Timeline:**
- Current version: Both methods supported (with warning)
- Next version: `ADMIN_ID_LIST` will still work but warning becomes more prominent
- Future version: `ADMIN_ID_LIST` support will be removed entirely

---

## Troubleshooting

### "Admin menu not showing"

**Cause:** Hash mismatch or typo in `.env` file.

**Solution:**
1. Regenerate the hash: `python -m utils.admin_hash_generator <your_telegram_id>`
2. Copy the EXACT hash to `.env` (no spaces, no line breaks)
3. Restart the bot

### "Security warning still showing"

**Cause:** `ADMIN_ID_HASHES` is empty or not set.

**Solution:**
1. Ensure `ADMIN_ID_HASHES=` is set in `.env` with at least one hash
2. Verify no extra spaces: `ADMIN_ID_HASHES=abc123...,def456...`
3. Restart the bot

### "How do I get my Telegram ID?"

Use [@userinfobot](https://t.me/userinfobot) on Telegram:
1. Start a chat with @userinfobot
2. Send any message
3. Copy the ID shown

---

## Security FAQ

### Q: Why hash admin IDs?

**A:** If an attacker gains read access to your `.env` file (via file inclusion vulnerability, backup leak, or misconfigured permissions), they can see your admin IDs. With hashing:
- Attacker cannot identify which Telegram accounts are admins
- Even with the hash, reverse engineering is impractical (Telegram ID space is 2^63)
- No impact on performance or functionality

### Q: Is SHA256 secure enough?

**A:** Yes. SHA256 is cryptographically secure and:
- Telegram IDs are 64-bit integers (9+ digits)
- Brute-forcing requires ~10^19 attempts
- Rainbow tables are impractical for this use case
- Collision attacks don't apply (we're not looking for collisions)

### Q: Can I use multiple admins?

**A:** Yes! Generate a hash for each admin ID and separate with commas:

```bash
python -m utils.admin_hash_generator 123456789
# Output: hash1

python -m utils.admin_hash_generator 987654321
# Output: hash2
```

Then in `.env`:
```env
ADMIN_ID_HASHES=hash1,hash2
```

### Q: What if I lose my admin hash?

**A:** Simply regenerate it:
```bash
python -m utils.admin_hash_generator <your_telegram_id>
```

The hash is deterministic - same ID always produces the same hash.

---

## Technical Details

### Hash Generation

```python
import hashlib

def generate_admin_id_hash(telegram_id: int | str) -> str:
    id_string = str(telegram_id)
    id_bytes = id_string.encode('utf-8')
    hash_obj = hashlib.sha256(id_bytes)
    return hash_obj.hexdigest()
```

### Verification Process

```python
def verify_admin_id(telegram_id: int | str, hash_list: list[str]) -> bool:
    user_hash = generate_admin_id_hash(telegram_id)
    return user_hash in hash_list
```

**Performance:** O(1) hash computation + O(n) list lookup where n = number of admins (typically 1-5).

---

## Support

If you encounter issues during migration:
1. Check the logs for detailed error messages
2. Verify your hash was generated correctly
3. Ensure no typos in `.env` file
4. Contact support with log excerpt (do NOT share your hash)

---

**Last Updated:** 2025-11-01
**Status:** Implemented and backward compatible
