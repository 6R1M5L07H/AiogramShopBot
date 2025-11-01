# GPG Backup Encryption

**Date:** 2025-11-01
**Priority:** Medium
**Status:** Planning
**Estimated Effort:** 2-3 hours
**Related:** Finding 5 (Database Backup System)

---

## Overview

Encrypt database backups using GPG public key encryption to protect sensitive data at rest.

**Current State:**
- Backups created and compressed (gzip)
- SHA256 checksums for integrity
- No encryption (plaintext backups)
- Backups contain sensitive data:
  - User Telegram IDs and usernames
  - Order and payment data
  - Encrypted shipping addresses (but encryption key in .env)
  - Wallet balances
  - Referral codes

**Desired State:**
- Backups encrypted with GPG public key
- Only private key holder can decrypt
- Encryption key separate from backups
- Production-ready security

---

## Security Benefits

### Why GPG Encryption?

1. **Asymmetric Encryption**
   - Encrypt with public key (stored in repo/config)
   - Decrypt with private key (kept secure, offline)
   - Bot doesn't need private key to create backups

2. **Protection Scenarios**
   - ✅ Backup files leaked/stolen → Cannot be decrypted
   - ✅ Server compromised → Backups remain encrypted
   - ✅ Unauthorized access to backup directory → Useless without private key
   - ✅ Accidental exposure → Data still protected

3. **Compliance**
   - GDPR compliance (data protection at rest)
   - Secure backup storage
   - Key rotation support

---

## Technical Specification

### Configuration

**File:** `.env` / `config.py`

```env
# GPG Backup Encryption
# Enable GPG encryption for database backups
# Requires: gnupg installed on system
GPG_BACKUP_ENCRYPTION_ENABLED=true

# Path to GPG public key file (ASCII-armored .asc file)
# This key is used to encrypt backups
# Private key is kept separately (offline, secure location)
#
# Generate keypair:
#   gpg --gen-key
#   gpg --armor --export your@email.com > backup-public.asc
#
# Example: ./keys/backup-public.asc
GPG_BACKUP_PUBLIC_KEY_FILE=./keys/backup-public.asc

# GPG key fingerprint (for verification)
# Optional but recommended for key validation
# Example: ABCD1234EFGH5678IJKL9012MNOP3456QRST7890
GPG_BACKUP_KEY_FINGERPRINT=

# Compression before encryption
# Options: none, gzip, bzip2
# Recommended: gzip (already implemented)
GPG_BACKUP_COMPRESS_BEFORE_ENCRYPT=gzip
```

---

## Implementation

### Phase 1: GPG Utilities (1 hour)

**File:** `utils/gpg_encryption.py`

**Features:**
- Import GPG public key from file
- Encrypt file with GPG public key
- Verify key fingerprint
- Error handling for missing GPG binary
- Fallback to unencrypted if GPG unavailable

**Example:**
```python
import gnupg
import logging
from pathlib import Path

class GPGEncryption:
    def __init__(self, public_key_path: str, fingerprint: str = None):
        self.gpg = gnupg.GPG()
        self.public_key = self._import_key(public_key_path)
        self.fingerprint = fingerprint

    def _import_key(self, key_path: Path) -> str:
        """Import GPG public key from file."""
        with open(key_path, 'r') as f:
            import_result = self.gpg.import_keys(f.read())

        if not import_result.fingerprints:
            raise ValueError(f"Failed to import GPG key from {key_path}")

        key_id = import_result.fingerprints[0]
        logging.info(f"GPG key imported: {key_id}")
        return key_id

    def encrypt_file(self, input_path: Path, output_path: Path) -> bool:
        """Encrypt file with GPG public key."""
        with open(input_path, 'rb') as f:
            encrypted = self.gpg.encrypt_file(
                f,
                recipients=[self.public_key],
                output=str(output_path),
                armor=False  # Binary output for smaller size
            )

        if not encrypted.ok:
            logging.error(f"GPG encryption failed: {encrypted.status}")
            return False

        logging.info(f"File encrypted: {output_path}")
        return True

    def verify_key_fingerprint(self) -> bool:
        """Verify imported key matches expected fingerprint."""
        if not self.fingerprint:
            return True  # Skip verification if no fingerprint configured

        keys = self.gpg.list_keys()
        for key in keys:
            if key['fingerprint'] == self.fingerprint:
                logging.info("GPG key fingerprint verified")
                return True

        logging.error(f"Key fingerprint mismatch! Expected: {self.fingerprint}")
        return False
```

---

### Phase 2: Backup Integration (1 hour)

**File:** `utils/db_backup.py` (modify existing)

**Changes:**
```python
def create_backup(self, compress: bool = True) -> Optional[Path]:
    # ... existing code ...

    # Compress backup if requested
    if compress:
        compressed_path = self._compress_backup(backup_path)
        if compressed_path:
            backup_path.unlink()  # Remove uncompressed file
            backup_path = compressed_path

    # NEW: Encrypt backup with GPG (if enabled)
    if config.GPG_BACKUP_ENCRYPTION_ENABLED:
        encrypted_path = self._encrypt_backup(backup_path)
        if encrypted_path:
            backup_path.unlink()  # Remove unencrypted file
            backup_path = encrypted_path

    # Create checksum file (for encrypted file)
    self._create_checksum(backup_path)

    return backup_path

def _encrypt_backup(self, backup_path: Path) -> Optional[Path]:
    """Encrypt backup with GPG public key."""
    try:
        from utils.gpg_encryption import GPGEncryption

        encrypted_path = backup_path.with_suffix(backup_path.suffix + ".gpg")
        logger.info(f"Encrypting backup: {encrypted_path}")

        gpg = GPGEncryption(
            config.GPG_BACKUP_PUBLIC_KEY_FILE,
            config.GPG_BACKUP_KEY_FINGERPRINT
        )

        if not gpg.encrypt_file(backup_path, encrypted_path):
            logger.error("GPG encryption failed, keeping unencrypted backup")
            return None

        original_size = backup_path.stat().st_size
        encrypted_size = encrypted_path.stat().st_size
        overhead = ((encrypted_size - original_size) / original_size) * 100
        logger.info(
            f"Backup encrypted: {original_size:,} -> {encrypted_size:,} bytes "
            f"({overhead:+.1f}% overhead)"
        )

        return encrypted_path

    except Exception as e:
        logger.error(f"Failed to encrypt backup: {e}", exc_info=True)
        return None
```

---

### Phase 3: Decryption Tool (30 minutes)

**File:** `utils/decrypt_backup.py` (CLI tool)

**Usage:**
```bash
# Decrypt backup with private key
python -m utils.decrypt_backup backups/db_backup_20251101_162300.db.gz.gpg

# Output: db_backup_20251101_162300.db.gz (decrypted)
```

**Implementation:**
```python
#!/usr/bin/env python3
"""
Decrypt GPG-encrypted backup files.

Usage:
    python -m utils.decrypt_backup <encrypted_backup.gpg>

Requires:
    - GPG private key in keyring
    - Passphrase (will be prompted)
"""

import gnupg
import sys
from pathlib import Path

def decrypt_backup(encrypted_path: str) -> bool:
    encrypted_file = Path(encrypted_path)

    if not encrypted_file.exists():
        print(f"Error: File not found: {encrypted_path}")
        return False

    # Remove .gpg extension
    decrypted_file = encrypted_file.with_suffix('')

    gpg = gnupg.GPG()

    print(f"Decrypting: {encrypted_file.name}")
    print(f"Output: {decrypted_file.name}")

    with open(encrypted_file, 'rb') as f:
        decrypted = gpg.decrypt_file(f, output=str(decrypted_file))

    if not decrypted.ok:
        print(f"Decryption failed: {decrypted.status}")
        return False

    print(f"✅ Decryption successful: {decrypted_file}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m utils.decrypt_backup <encrypted_backup.gpg>")
        sys.exit(1)

    success = decrypt_backup(sys.argv[1])
    sys.exit(0 if success else 1)
```

---

### Phase 4: Documentation (30 minutes)

**File:** `docs/BACKUP_RESTORATION_GUIDE.md`

**Sections:**
1. Backup File Format
2. GPG Encryption Details
3. Decryption Instructions
4. Restoration Steps
5. Key Management Best Practices

---

## File Naming Convention

**Encrypted Backup:**
```
db_backup_20251101_162300.db.gz.gpg
```

**Components:**
- `db_backup_` - Prefix
- `20251101_162300` - Timestamp (YYYYMMDD_HHMMSS)
- `.db` - SQLite database
- `.gz` - Gzip compressed
- `.gpg` - GPG encrypted

**Checksum:**
```
db_backup_20251101_162300.db.gz.gpg.sha256
```

---

## Dependencies

### Python Package

```bash
pip install python-gnupg
```

**Requirements.txt:**
```
python-gnupg>=0.5.0
```

### System Requirement

**Linux/macOS:**
```bash
# Ubuntu/Debian
apt-get install gnupg

# macOS
brew install gnupg
```

**Check Installation:**
```bash
gpg --version
```

---

## Key Generation Guide

### 1. Generate GPG Keypair

```bash
gpg --gen-key
```

**Prompts:**
- Name: "ShopBot Backup Encryption"
- Email: backup@yourshop.com
- Passphrase: (strong passphrase, store securely!)

### 2. Export Public Key

```bash
# Export public key (store in repo)
gpg --armor --export backup@yourshop.com > keys/backup-public.asc

# Get fingerprint
gpg --fingerprint backup@yourshop.com
```

### 3. Export Private Key (SECURE!)

```bash
# Export private key (NEVER commit to repo!)
gpg --armor --export-secret-keys backup@yourshop.com > backup-private.asc

# Store in:
# - Password manager (encrypted)
# - USB drive (offline, encrypted)
# - Secure backup location
```

### 4. Add to Configuration

```env
GPG_BACKUP_ENCRYPTION_ENABLED=true
GPG_BACKUP_PUBLIC_KEY_FILE=./keys/backup-public.asc
GPG_BACKUP_KEY_FINGERPRINT=ABCD1234...
```

---

## Testing Checklist

### Setup
- [ ] Install gnupg on system
- [ ] Generate test GPG keypair
- [ ] Export public key to keys/ directory
- [ ] Configure .env with GPG settings

### Encryption
- [ ] Create backup → Encrypted file created (.gpg)
- [ ] Verify encrypted file is binary (not readable)
- [ ] Check file size (compressed + ~1-2% GPG overhead)
- [ ] Checksum file created for encrypted file

### Decryption
- [ ] Decrypt backup with private key
- [ ] Verify decrypted file matches original (checksum)
- [ ] Restore database from decrypted backup
- [ ] Bot starts successfully with restored database

### Error Handling
- [ ] GPG not installed → Warning, fallback to unencrypted
- [ ] Invalid public key → Error, backup creation fails
- [ ] Missing public key file → Error, backup creation fails
- [ ] Wrong fingerprint → Warning, encryption continues

---

## Security Best Practices

### Production Deployment

1. **Key Storage**
   - ✅ Public key in repo (safe, used for encryption)
   - ❌ Private key NEVER in repo
   - ✅ Private key in secure vault (offline, encrypted USB, KMS)

2. **Key Rotation**
   - Rotate keys annually
   - Keep old keys for decrypting old backups
   - Document key rotation process

3. **Access Control**
   - Limit who has access to private key
   - Require multi-person approval for key access
   - Log all key usage

4. **Backup Strategy**
   - Keep encrypted backups on untrusted storage (cloud, NAS)
   - Keep private key separate from backups
   - Test restoration procedure regularly (quarterly)

---

## Backup Restoration Flow

```
1. Locate encrypted backup: db_backup_20251101_162300.db.gz.gpg
2. Verify checksum: sha256sum -c db_backup_20251101_162300.db.gz.gpg.sha256
3. Decrypt: python -m utils.decrypt_backup db_backup_20251101_162300.db.gz.gpg
   → Output: db_backup_20251101_162300.db.gz
4. Decompress: gunzip db_backup_20251101_162300.db.gz
   → Output: db_backup_20251101_162300.db
5. Restore: cp db_backup_20251101_162300.db data/database.db
6. Start bot: python run.py
```

---

## Implementation Order

1. **Phase 1**: GPG Utilities (utils/gpg_encryption.py)
2. **Phase 2**: Backup Integration (modify utils/db_backup.py)
3. **Phase 3**: Decryption Tool (utils/decrypt_backup.py)
4. **Phase 4**: Documentation (BACKUP_RESTORATION_GUIDE.md)
5. **Phase 5**: Testing (full encryption/decryption cycle)

---

## Future Enhancements

### Phase 2 (Optional)
- [ ] Multiple recipient keys (multiple admins)
- [ ] Key rotation automation
- [ ] Encrypted backup verification (decrypt in temp, verify, delete)
- [ ] Remote backup to encrypted cloud storage

---

## Related TODOs

- 2025-10-19_TODO_gpg-public-key-display.md (GPG key display for users)
- 2025-11-01_TODO_vault-integration.md (Alternative: Vault for secrets)
- 2025-10-22_TODO_security-audit-findings.md (Finding 5: Database Backups)

---

## Notes

- GPG encryption adds ~1-2% file size overhead
- Backup creation time increases by ~0.5-1 second (negligible)
- Private key passphrase required for decryption
- Compatible with standard GPG tools (no proprietary formats)

---

**Status:** Ready for Implementation
**Branch:** `technical-debt` or `feature/backup-encryption`
