# Database Restore Script - Implementation Plan

## Status: PLANNING PHASE
**Last Updated**: 2025-01-30
**Branch**: fix/backup-event-loop-blocking (after backup implementation is tested)

## Requirements (User Confirmed)

1. **GPG Private Key Input**: Base64-encoded, interactive prompt or stdin (NO disk files)
2. **Passphrase**: Interactive input via `getpass`
3. **Docker Integration**: Script stops/starts containers automatically
4. **Pre-Restore Backup**: Automatic backup using existing `DatabaseBackup.create_backup()`
5. **Restore Target**: Support both production DB and custom path (via `--target-path` flag)
6. **Error Handling**: Automatic rollback to pre-restore backup on failure

## Critical: Dual-Mode Database Encryption Support

### Mode 1: Standard SQLite (DB_ENCRYPTION=false)
```
GPG Encrypted Backup (.db.gz.gpg)
  ↓ GPG decrypt with in-memory private key (RAM)
  ↓ gzip decompress (RAM)
  ↓ SQL statements (plaintext SQL dump in RAM)
  ↓ Parse and execute directly on sqlite3.connect()
  ↓ Standard SQLite DB
```

**Implementation**:
```python
conn = sqlite3.connect(target_path)
conn.execute("BEGIN TRANSACTION")
for statement in parse_sql_statements(sql_buffer):
    conn.execute(statement)
conn.execute("COMMIT")
```

### Mode 2: SQLCipher Encrypted (DB_ENCRYPTION=true)
```
GPG Encrypted Backup (.db.gz.gpg)
  ↓ GPG decrypt with in-memory private key (RAM)
  ↓ gzip decompress (RAM)
  ↓ SQL statements (plaintext SQL dump in RAM)
  ↓ Parse and execute on sqlcipher.connect() WITH PRAGMA key
  ↓ SQLCipher Encrypted DB
```

**Implementation**:
```python
from sqlcipher3 import dbapi2 as sqlcipher
conn = sqlcipher.connect(target_path)
conn.execute(f"PRAGMA key = '{config.DB_PASS}'")  # CRITICAL!
conn.execute("BEGIN TRANSACTION")
for statement in parse_sql_statements(sql_buffer):
    conn.execute(statement)
conn.execute("COMMIT")
```

**Key Difference**:
- Both modes start with GPG-encrypted backup
- Both decrypt to plaintext SQL dump in memory
- **Difference is only in the target DB connection**:
  - Standard SQLite: `sqlite3.connect()`
  - SQLCipher: `sqlcipher.connect() + PRAGMA key`

## Architecture

### File Structure
```
scripts/
  restore_db.py          # Standalone CLI script (~350 lines)
```

### Memory-Only Pipeline
```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: GPG Private Key Handling (In-Memory)              │
│  ─────────────────────────────────────────────────────────  │
│  User Input: Base64-encoded private key                     │
│    ↓ Decode base64 (RAM)                                    │
│    ↓ Import to temporary GPG keyring (RAM only)             │
│  GPG keyring ready for decryption                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Pre-Restore Safety                                │
│  ─────────────────────────────────────────────────────────  │
│  1. Verify checksum of backup file                          │
│  2. Create pre-restore backup using DatabaseBackup          │
│  3. Stop Docker containers (docker-compose stop)            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Decrypt and Decompress (In-Memory)                │
│  ─────────────────────────────────────────────────────────  │
│  Encrypted Backup File (.db.gz.gpg)                         │
│    ↓ gpg.decrypt_file() with in-memory key (RAM)            │
│  Compressed SQL Buffer (io.BytesIO in RAM)                  │
│    ↓ gzip.decompress() (RAM)                                │
│  Plaintext SQL Buffer (io.BytesIO in RAM)                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: Parse SQL (Streaming, In-Memory)                  │
│  ─────────────────────────────────────────────────────────  │
│  SQL Buffer (io.BytesIO)                                    │
│    ↓ Stream line-by-line                                    │
│    ↓ State machine parser (handle multi-line, strings)      │
│  Generator yielding SQL statements (one at a time)          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5: Execute on Target DB (Dual-Mode)                  │
│  ─────────────────────────────────────────────────────────  │
│  IF config.DB_ENCRYPTION == False:                          │
│    conn = sqlite3.connect(target_path)                      │
│  ELSE:                                                       │
│    conn = sqlcipher.connect(target_path)                    │
│    conn.execute(f"PRAGMA key = '{config.DB_PASS}'")         │
│                                                              │
│  conn.execute("BEGIN TRANSACTION")                          │
│  for statement in sql_statements:                           │
│      conn.execute(statement)                                │
│  conn.execute("COMMIT")                                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 6: Cleanup and Restart                               │
│  ─────────────────────────────────────────────────────────  │
│  1. Delete GPG private key from keyring                     │
│  2. Clear all in-memory buffers                             │
│  3. Start Docker containers (docker-compose start)          │
│  4. Verify database integrity                               │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### SQL Statement Parser (Critical Component)
**Challenge**: SQL dump contains complex statements with:
- Multi-line CREATE TABLE statements
- String values containing semicolons
- Binary data (X'...' format)
- Comments (-- and /* */)

**Solution**: State Machine Parser
```python
def parse_sql_statements(buffer: io.BytesIO) -> Generator[str, None, None]:
    """Stream-parse SQL statements from buffer.

    Handles:
    - Multi-line statements
    - Strings with semicolons
    - Comments
    """
    current_statement = []
    in_string = False
    escape_next = False

    for line in buffer:
        # State machine logic
        # ...

        if statement_complete and not in_string:
            yield ''.join(current_statement)
            current_statement = []
```

### Error Handling with Automatic Rollback
```python
try:
    # Phase 2: Pre-restore backup
    pre_restore_backup = create_pre_restore_backup()

    # Phase 3-5: Restore
    restore_from_encrypted_backup(backup_path, target_path)

    print("✅ Restore successful!")

except Exception as e:
    print(f"❌ Restore failed: {e}")
    print("🔄 Rolling back to pre-restore backup...")

    # Automatic rollback
    shutil.copy2(pre_restore_backup, target_path)

    print("✅ Rollback successful - database restored to pre-restore state")
    raise

finally:
    # Cleanup
    cleanup_gpg_key()
    start_docker_containers()
```

### GPG Private Key Handling (Memory-Only)
```python
def import_gpg_key_from_input() -> str:
    """Import GPG private key from base64 input (memory-only).

    Returns:
        Key fingerprint for cleanup
    """
    print("Please paste base64-encoded GPG private key:")
    print("(Press Ctrl+D when done)")

    base64_key = sys.stdin.read().strip()

    # Decode base64 to ASCII-armored key
    key_ascii = base64.b64decode(base64_key).decode('utf-8')

    # Import to in-memory GPG keyring
    gpg = gnupg.GPG()
    import_result = gpg.import_keys(key_ascii)

    if not import_result.fingerprints:
        raise RuntimeError("Failed to import GPG private key")

    fingerprint = import_result.fingerprints[0]
    print(f"✅ GPG key imported: {fingerprint[:16]}...")

    return fingerprint
```

## Security Guarantees

### What NEVER Touches Disk
1. ✅ GPG private key (only in GPG's in-memory keyring)
2. ✅ GPG passphrase (only in RAM via getpass)
3. ✅ Decrypted backup data (only in io.BytesIO buffers)
4. ✅ Plaintext SQL statements (only in RAM during parsing)
5. ✅ Intermediate decompression buffers

### What IS Written to Disk
1. ✅ Pre-restore backup (encrypted with GPG if PGP_PUBLIC_KEY_BASE64 set)
2. ✅ Final target database (encrypted with SQLCipher if DB_ENCRYPTION=true)

## Usage Examples

### Example 1: Restore Production DB (Interactive)
```bash
# Navigate to bot directory
cd /path/to/shopbot

# Run restore script
python scripts/restore_db.py backups/db_backup_20250130_120000.db.gz.gpg

# Script prompts:
# 1. "Please paste base64-encoded GPG private key:"
#    → User pastes key, presses Ctrl+D
# 2. "Enter GPG key passphrase:"
#    → User enters passphrase (hidden)
# 3. "⚠️  Warning: This will restore over production database. Continue? [y/N]"
#    → User types 'y'

# Output:
# ✅ Checksum verified
# ✅ Pre-restore backup created: data/shop.db.backup-20250130-153045
# 🛑 Stopping Docker containers...
# ✅ Containers stopped
# 🔓 Decrypting backup...
# 📦 Decompressing...
# 📝 Parsing SQL statements...
# ⚙️  Executing restore (SQLCipher mode)...
# ✅ Restore successful!
# 🔄 Starting Docker containers...
# ✅ Containers started
# ✅ Database restored successfully
```

### Example 2: Restore to Test DB (Pipe Key)
```bash
# Pipe GPG key from file
cat private_key.asc | base64 | python scripts/restore_db.py \
    backups/db_backup_20250130_120000.db.gz.gpg \
    --target-path test.db \
    --no-restart \
    --key-stdin

# Only prompts for passphrase
# No container restart
```

### Example 3: Restore with Error (Automatic Rollback)
```bash
python scripts/restore_db.py corrupted_backup.db.gz.gpg

# Output:
# ✅ Checksum verified
# ✅ Pre-restore backup created: data/shop.db.backup-20250130-153100
# 🛑 Stopping Docker containers...
# ✅ Containers stopped
# 🔓 Decrypting backup...
# 📦 Decompressing...
# 📝 Parsing SQL statements...
# ⚙️  Executing restore...
# ❌ Restore failed: SQL syntax error at line 1234
# 🔄 Rolling back to pre-restore backup...
# ✅ Rollback successful - database restored to pre-restore state
# 🔄 Starting Docker containers...
# ✅ Containers started
```

## CLI Arguments

```
usage: restore_db.py [-h] [--target-path PATH] [--no-restart]
                     [--key-stdin] [--skip-backup] [--force]
                     backup_file

Restore database from encrypted backup (memory-only)

positional arguments:
  backup_file           Path to encrypted backup file (.db.gz.gpg)

optional arguments:
  -h, --help            Show this help message
  --target-path PATH    Custom target database path (default: from config)
  --no-restart          Skip Docker container restart
  --key-stdin           Read GPG private key from stdin (base64-encoded)
  --skip-backup         Skip pre-restore backup (DANGEROUS!)
  --force               Skip confirmation prompts
```

## Testing Strategy

### Unit Tests
1. ✅ SQL statement parser with edge cases (strings, comments, multi-line)
2. ✅ GPG key import/cleanup (mock GPG)
3. ✅ Dual-mode connection logic (SQLite vs SQLCipher)

### Integration Tests
1. ✅ Full restore flow with test backup (SQLite mode)
2. ✅ Full restore flow with test backup (SQLCipher mode)
3. ✅ Error handling with rollback
4. ✅ Memory-only verification (no temp files created)

### Manual Testing Checklist
- [ ] Restore to production DB (SQLite mode)
- [ ] Restore to production DB (SQLCipher mode)
- [ ] Restore to custom path
- [ ] Restore with invalid GPG key
- [ ] Restore with wrong passphrase
- [ ] Restore with corrupted backup (triggers rollback)
- [ ] Restore with Docker containers already stopped
- [ ] Pipe GPG key from stdin

## Open Questions / Decisions Needed

1. **GPG Key Cleanup**: Should we delete the key from GPG keyring even on error?
   - **Recommendation**: YES - cleanup in `finally` block for security

2. **Pre-Restore Backup Encryption**: Should pre-restore backup be encrypted?
   - **Recommendation**: YES if PGP_PUBLIC_KEY_BASE64 is set (use existing backup logic)

3. **Docker Compose File**: Which file to use? (dev vs prod)
   - **Recommendation**: Auto-detect based on `config.RUNTIME_ENVIRONMENT`

4. **Verification After Restore**: Should we verify DB integrity?
   - **Recommendation**: YES - run `PRAGMA integrity_check` after restore

5. **Progress Reporting**: Show progress for large restores?
   - **Recommendation**: YES - show statement count every 1000 statements

## Files to Create/Modify

### New Files
- `scripts/restore_db.py` (~400 lines)

### Files to Update
- `docs/database_backup_architecture.md` (add restore section)

## Next Steps (After Current Backup Testing)

1. Wait for backup implementation test results
2. If tests pass: Implement restore script on same branch
3. Add restore documentation
4. Test restore with both database modes
5. Commit and push
6. Update PR description

## Notes
- Implementation should reuse existing adapter pattern where possible
- Keep security as top priority (memory-only operations)
- Comprehensive error handling with clear user feedback
- Make it bulletproof - this is a disaster recovery tool