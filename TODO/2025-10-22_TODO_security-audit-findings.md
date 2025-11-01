# Security Audit Findings - Implementation Tasks

**Date:** 2025-10-22
**Priority:** High
**Status:** Planning
**Estimated Effort:** High (4-6 hours)
**Source:** Copilot Security Audit

---

## Overview

This document tracks security improvements identified during a Copilot security audit of the AiogramShopBot codebase. These findings address critical security, logging, and operational concerns.

---

## Finding 1: Missing Rate Limiting Variables ✅ IMPLEMENTED

**Status:** ✅ COMPLETED (2025-11-01)

**Issue:**
Rate limiting configuration variables are missing, leaving the system vulnerable to abuse and DoS attacks.

**Required Variables:**
```env
MAX_ORDERS_PER_USER_PER_HOUR=5
MAX_PAYMENT_CHECKS_PER_MINUTE=10
```

**Implementation Tasks:**
- [x] Add to `.env.template` with documentation
- [x] Implement rate limiting in order creation endpoint
- [ ] Implement rate limiting for payment status checks (Future: if needed)
- [x] Add Redis-based rate limiting (using existing Redis connection)
- [x] Add user notification when rate limit exceeded
- [ ] Add admin alert for suspected abuse patterns (Future: monitoring dashboard)

**Files to Modify:**
- `.env.template` (✅ Done)
- `config.py` - Add new config variables
- `services/order.py` - Add rate limiting check before order creation
- `processing/processing.py` - Add rate limiting for payment checks
- `middleware/rate_limit.py` - New middleware for rate limiting

---

## Finding 2: Admin ID List Security Issue ✅ RESOLVED (REVISED APPROACH)

**Status:** ✅ COMPLETED (2025-11-01) - Pragmatic solution implemented

**Issue:**
Admin IDs are stored in plaintext in `.env` and can be read directly from the environment. If an attacker gains access to environment variables, they know exactly which Telegram IDs have admin privileges.

**Current Implementation:**
```env
ADMIN_ID_LIST=123456789,987654321
```

**Proposed Solution:**
Use hashed admin IDs for verification:

```env
# Generate with: echo -n "123456789" | sha256sum
ADMIN_ID_HASHES=abc123...,def456...
```

**REVISED IMPLEMENTATION (See docs/security/ADMIN_SECURITY_CLARIFICATION.md):**
- [x] Create utility script to generate admin ID hashes (utils/admin_hash_generator.py)
- [x] Update `config.py` to generate hashes at runtime from plaintext IDs
- [x] Modify admin verification to use hash-based comparison (defense-in-depth)
- [x] Document design decision and security trade-offs
- [x] Maintain plaintext IDs for notification functionality (required by Telegram API)

**REASON FOR REVISION:**
Original proposal (hash-only storage) breaks core functionality. Telegram bots MUST know plaintext user IDs to send messages (notifications, alerts, startup messages). The implemented solution provides defense-in-depth while maintaining all features.

**Implementation Tasks:**
- [x] Create utility script (utils/admin_hash_generator.py)
- [x] Runtime hash generation in config.py
- [x] Hash-based verification in custom_filters.py
- [x] Comprehensive documentation (ADMIN_SECURITY_CLARIFICATION.md)
- [x] File permission best practices documented

**Security Benefits:**
- Attacker can't identify admin accounts even with env access
- Requires rainbow table or brute force to reverse (impractical for large ID space)
- No impact on functionality (same verification speed)

**Files to Modify:**
- `.env.template` - Update ADMIN_ID_LIST to ADMIN_ID_HASHES with instructions
- `config.py` - Read and parse hashes
- `utils/admin_hash_generator.py` - New utility script
- All files checking `is_admin()` - Update to hash-based verification

---

## Finding 3: Logging Configuration Missing ✅ IMPLEMENTED

**Status:** ✅ COMPLETED (2025-11-01)

**Issue:**
No centralized logging configuration:
- No log level control (always DEBUG in production?)
- No log rotation (disk space issues)
- No secret masking (credentials could leak in logs)
- No forensic analysis capability

**Required Variables:**
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_MASK_SECRETS=true
LOG_ROTATION_DAYS=7
```

**Implementation Tasks:**
- [x] Add to `.env.template` with documentation
- [x] Implement centralized logging configuration (utils/logging_config.py)
- [x] Add log rotation using `logging.handlers.TimedRotatingFileHandler`
- [x] Implement secret masking for:
  - [x] API keys (KRYPTO_EXPRESS_API_KEY, KRYPTO_EXPRESS_API_SECRET)
  - [x] Tokens (TOKEN, WEBHOOK_SECRET_TOKEN, NGROK_TOKEN)
  - [x] Passwords (DB_PASS, REDIS_PASSWORD)
  - [x] Private data (item content, addresses)
  - [x] Payment addresses and transaction hashes
  - [x] Email addresses and phone numbers
- [ ] Add structured logging (JSON format for parsing) (Future: if log aggregation needed)
- [ ] Create log analysis script for security events (Future: monitoring dashboard)

**Recommended Log Structure:**
```python
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'detailed': {
            'class': 'logging.Formatter',
            'format': '%(asctime)s %(name)-15s %(levelname)-8s %(message)s'
        }
    },
    'filters': {
        'secret_masker': {
            '()': 'utils.logging.SecretMaskingFilter'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': 'bot.log',
            'when': 'midnight',
            'interval': 1,
            'backupCount': config.LOG_ROTATION_DAYS,
            'formatter': 'detailed',
            'filters': ['secret_masker']
        }
    }
}
```

**Files to Create:**
- `utils/logging.py` - SecretMaskingFilter implementation
- `logging_config.py` - Centralized logging configuration

**Files to Modify:**
- `.env.template` (✅ Done)
- `config.py` - Add logging config variables
- `main.py` - Initialize logging configuration on startup

---

## Finding 4: Webhook Security Headers Missing ✅ IMPLEMENTED

**Status:** ✅ COMPLETED (2025-11-01)

**Issue:**
Webhook endpoints lack security headers:
- No Content-Security-Policy (CSP)
- No CORS configuration
- No X-Content-Type-Options
- No X-Frame-Options

**Required Variables:**
```env
WEBHOOK_CSP_ENABLED=true
WEBHOOK_CORS_ALLOWED_ORIGINS=https://kryptoexpress.pro
WEBHOOK_SECURITY_HEADERS_ENABLED=true
WEBHOOK_HSTS_ENABLED=false
```

**Implementation Tasks:**
- [x] Add to `.env.template` with comprehensive documentation
- [x] Add CSP middleware for FastAPI endpoints
- [x] Configure CORS for webhook endpoints
- [x] Add security headers middleware:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: no-referrer-when-downgrade`
  - `Permissions-Policy: (disable dangerous features)`
  - `Strict-Transport-Security` (optional, HTTPS only)

**Files Created:**
- `middleware/security_headers.py` - SecurityHeadersMiddleware and CSPMiddleware

**Files Modified:**
- `.env.template` - Added comprehensive webhook security documentation
- `config.py` - Added security configuration variables
- `bot.py` - Integrated security middleware (SecurityHeaders, CSP, CORS)

**Features Implemented:**
- Configurable security headers middleware
- Content Security Policy with restrictive defaults
- CORS support for payment webhooks
- HSTS support (disabled by default, HTTPS only)
- Permissions Policy to disable dangerous browser features
- All middleware conditionally enabled via configuration

---

## Finding 5: Database Backup Configuration Missing ✅ IMPLEMENTED

**Status:** ✅ COMPLETED (2025-11-01)

**Issue:**
No backup configuration for SQLite database:
- No automated backups
- No backup retention policy
- Risk of data loss

**Required Variables:**
```env
DB_BACKUP_ENABLED=true
DB_BACKUP_INTERVAL_HOURS=6
DB_BACKUP_RETENTION_DAYS=7
DB_BACKUP_PATH=/backups
```

**Implementation Tasks:**
- [x] Add to `.env.template` with documentation
- [x] Create backup service with scheduled job
- [x] Implement SQLite backup using `.backup()` method
- [x] Add backup rotation (delete old backups)
- [x] Add backup compression (gzip)
- [x] Add backup integrity check (SHA256 checksums)
- [x] Add admin notification on backup failure
- [x] Create backups directory and gitignore rules

**Files Created:**
- `jobs/database_backup_job.py` - Scheduled backup service with admin notifications
- `utils/db_backup.py` - Complete backup utilities (create, verify, restore, cleanup)
- `backups/.gitkeep` - Backup directory placeholder

**Files Modified:**
- `.env.template` - Added comprehensive backup configuration documentation
- `config.py` - Added backup config variables
- `bot.py` - Integrated backup scheduler in startup/shutdown
- `.gitignore` - Added backup file exclusions

**Features Implemented:**
- Automated backups at configurable intervals (default: 6 hours)
- Gzip compression with size reporting
- SHA256 checksum generation and verification
- Automatic cleanup of old backups (default: 7 days retention)
- Admin notifications on backup failures
- Manual backup trigger function
- Backup restore capability with pre-restore safety backup
- Graceful startup/shutdown integration

---

## Finding 6: Inconsistent Naming Conventions

**Status:** ⚠️ Requires refactoring

**Issue:**
Inconsistent environment variable naming:
- `WEBAPP_HOST` uses `_HOST` suffix
- `KRYPTO_EXPRESS_API_URL` uses `_URL` suffix
- Mixing URL/HOST/PORT patterns

**Proposal:**
Standardize on:
- Use `_URL` for full URLs (with protocol and path)
- Use `_HOST` + `_PORT` for separate host/port
- Use `_BASE_URL` for API base URLs (no path)

**Examples:**
```env
# Full URLs
KRYPTO_EXPRESS_API_BASE_URL=https://kryptoexpress.pro/api

# Host + Port (for services we control)
WEBAPP_HOST=localhost
WEBAPP_PORT=5001
REDIS_HOST=localhost
REDIS_PORT=6379
```

**Implementation Tasks:**
- [ ] Audit all environment variables
- [ ] Create naming convention standard document
- [ ] Refactor variable names for consistency
- [ ] Update all references in code
- [ ] Update `.env.template` with new names
- [ ] Create migration script for existing `.env` files
- [ ] Add deprecation warnings for old names (keep backward compatibility for 2 releases)

**Files to Modify:**
- `.env.template`
- `config.py`
- All files reading affected config variables

---

## Finding 7: Environment-Specific Templates Missing

**Status:** ⚠️ Not started

**Issue:**
Single `.env.template` for both development and production:
- DEV needs ngrok, PROD doesn't
- Different security requirements
- Different rate limits
- Confusing for new developers

**Proposal:**
Create separate templates:

**`.env.dev.template`** (Development):
```env
RUNTIME_ENVIRONMENT=DEV
NGROK_TOKEN=  # Required for DEV
DB_ENCRYPTION=false  # Faster for dev
LOG_LEVEL=DEBUG
MAX_ORDERS_PER_USER_PER_HOUR=100  # Relaxed for testing
WEBHOOK_SECURITY_HEADERS_ENABLED=false  # Optional for local dev
```

**`.env.prod.template`** (Production):
```env
RUNTIME_ENVIRONMENT=PROD
NGROK_TOKEN=  # Not needed
DB_ENCRYPTION=true  # Security
LOG_LEVEL=INFO
MAX_ORDERS_PER_USER_PER_HOUR=5  # Strict limits
WEBHOOK_SECURITY_HEADERS_ENABLED=true  # Required
```

**Implementation Tasks:**
- [ ] Create `.env.dev.template` with dev-optimized defaults
- [ ] Create `.env.prod.template` with production-optimized defaults
- [ ] Update README.md with instructions for both templates
- [ ] Add validation script to check production settings
- [ ] Keep existing `.env.template` as universal fallback

**Files to Create:**
- `.env.dev.template`
- `.env.prod.template`
- `scripts/validate_prod_config.py` - Validates production settings

**Files to Modify:**
- `README.md` - Update setup instructions
- `.env.template` - Add notice about environment-specific templates

---

## Implementation Priority

### Phase 1: Critical Security (Week 1)
1. **Finding 2: Admin ID Hashing** ⚠️ CRITICAL
   - Prevents identification of admin accounts
   - Quick win with high security impact

2. **Finding 1: Rate Limiting Implementation** ⚠️ HIGH
   - Prevents abuse and DoS attacks
   - Protects payment system integrity

### Phase 2: Operational Improvements (Week 2)
3. **Finding 3: Logging Configuration** ⚠️ HIGH
   - Essential for debugging and forensics
   - Prevents credential leaks

4. **Finding 5: Database Backups** ⚠️ MEDIUM
   - Prevents data loss
   - Required for business continuity

### Phase 3: Hardening (Week 3)
5. **Finding 4: Webhook Security Headers** ⚠️ MEDIUM
   - Defense-in-depth security layer
   - Industry best practice

6. **Finding 7: Environment Templates** ⚠️ LOW
   - Developer experience improvement
   - Reduces configuration errors

7. **Finding 6: Naming Conventions** ⚠️ LOW
   - Code quality improvement
   - Low urgency, high effort

---

## Finding 8: Hide Zero-Stock Items from Catalog

**Status:** ✅ ALREADY IMPLEMENTED (Verified 2025-11-01)

**Issue:**
Items with 0 available quantity are still shown in the catalog, confusing users who cannot purchase them.

**Current Behavior:**
- Subcategories shown even when all items are sold/reserved
- Shows "0 available" but item is still clickable
- Poor user experience

**Desired Behavior:**
- Hide subcategories from catalog when available quantity = 0
- Only show purchasable items
- Cleaner catalog display

**Implementation Tasks:**
- [x] Modify `SubcategoryService.get_buttons()` to filter out zero-stock subcategories (ALREADY DONE)
- [x] Update subcategory query to check available quantity (ALREADY DONE - Line 29-31 in services/subcategory.py)
- [ ] Add test case for zero-stock filtering (Future: comprehensive test suite)

**VERIFICATION:**
Code at services/subcategory.py:29-31 already implements this:
```python
# Skip subcategories with zero stock (sold out or all reserved) or no items
if available_qty == 0 or item is None:
    continue
```

NO ACTION REQUIRED - Feature already working as intended.

**Files to Modify:**
- `services/subcategory.py` - Filter subcategories by available qty > 0
- `repositories/subcategory.py` - Add available_qty check to query (optional)

---

## Testing Checklist

After implementation, verify:

- [ ] Rate limiting works correctly (test with multiple orders)
- [ ] Admin authentication works with hashed IDs
- [ ] Logs rotate correctly
- [ ] Secrets are masked in logs
- [ ] Backups run on schedule
- [ ] Backup restore works correctly
- [ ] Security headers present in webhook responses
- [ ] CORS configuration allows KryptoExpress webhooks
- [ ] Both dev and prod templates produce working configs

---

## Related Documentation

- [Payment Validation System](./2025-10-22_TODO_payment-validation-followup.md)
- [Strike System](./2025-10-19_TODO_strike-system-and-user-ban.md)

---

## Notes

- All security findings should be treated as high priority
- Admin ID hashing is backward-incompatible - plan migration carefully
- Logging changes may impact disk usage - monitor after deployment
- Backup system should be tested thoroughly before production use
