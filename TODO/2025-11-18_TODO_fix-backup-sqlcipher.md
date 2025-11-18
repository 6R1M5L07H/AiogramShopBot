# TODO: Fix Database Backup and Data Retention for SQLCipher Mode

**Created:** 2025-11-18
**Priority:** Medium
**Status:** Open

## Problem

Two system jobs fail when SQLCipher encryption is enabled:

1. **Database Backup Job** (`utils/db_backup.py`)
   - Error: `file is not a database`
   - Root cause: Uses `sqlite3.connect()` instead of `sqlcipher3`
   - Encrypted databases cannot be opened without proper SQLCipher connection

2. **Data Retention Cleanup Job** (`jobs/data_retention_cleanup_job.py`)
   - Error: `TypeError: object ChunkedIteratorResult can't be used in 'await' expression`
   - Root cause: Uses `await` on synchronous session results in SQLCipher mode
   - Missing dual-mode session handling

## Impact

- **Backup Job:** Automated backups fail silently (logs only)
- **Data Retention:** Old shipping addresses and referral data not deleted (GDPR risk)
- **Severity:** Medium (workarounds exist, not critical for operation)

## Tasks

### 1. Fix Database Backup (`utils/db_backup.py`)

**Current Code:**
```python
conn = sqlite3.connect(source_path)
```

**Required Changes:**
- Check if `DB_ENCRYPTION` is enabled in config
- If enabled: Use `sqlcipher3` with `PRAGMA key`
- If disabled: Use standard `sqlite3`

**Implementation:**
```python
if config.DB_ENCRYPTION:
    import pysqlcipher3.dbapi2 as sqlcipher
    conn = sqlcipher.connect(source_path)
    conn.execute(f"PRAGMA key = '{config.DATABASE_ENCRYPTION_KEY}'")
else:
    import sqlite3
    conn = sqlite3.connect(source_path)
```

**Files to modify:**
- `utils/db_backup.py` (lines ~40-50)

### 2. Fix Data Retention Cleanup (`jobs/data_retention_cleanup_job.py`)

**Current Code:**
```python
result = await session.execute(stmt)
expired_addresses = result.scalars().all()
```

**Problem:**
- SQLCipher uses synchronous `Session`, not `AsyncSession`
- Cannot use `await` on synchronous operations

**Required Changes:**
- Use `db.session_execute()` wrapper instead of direct `await session.execute()`
- Wrapper handles both `AsyncSession` and `Session` modes

**Implementation:**
```python
from db import session_execute, session_commit

result = await session_execute(stmt, session)  # Works for both modes
expired_addresses = result.scalars().all()

# Later:
await session_commit(session)  # Works for both modes
```

**Files to modify:**
- `jobs/data_retention_cleanup_job.py` (multiple locations)

### 3. Testing

**Test Scenarios:**
1. **Without SQLCipher:**
   - Backup should succeed using `sqlite3`
   - Data retention should delete old records

2. **With SQLCipher:**
   - Backup should succeed using `sqlcipher3`
   - Data retention should delete old records
   - No `await` errors on synchronous sessions

**Test Commands:**
```bash
# Test backup manually
python -c "from jobs.database_backup_job import perform_backup; import asyncio; asyncio.run(perform_backup())"

# Test data retention manually
python -c "from jobs.data_retention_cleanup_job import cleanup_expired_data; import asyncio; asyncio.run(cleanup_expired_data())"
```

## References

- **Related Issue:** Discovered during PGP shipping encryption testing (2025-11-18)
- **Architecture Pattern:** Dual-mode session handling (see `db.py`)
- **Lesson Learned #19:** ALWAYS use `db.py` wrapper functions for database operations

## Notes

- Both jobs are non-critical for immediate operation
- Backup job was introduced in recent feature (database backup automation)
- Data retention is important for GDPR compliance (30-day shipping address deletion)
- SQLCipher mode is optional (disabled by default)

## Acceptance Criteria

- [ ] Backup job succeeds with SQLCipher enabled
- [ ] Data retention job completes without errors in both modes
- [ ] Tests pass for both encrypted and unencrypted databases
- [ ] Error notifications stop appearing in production logs
