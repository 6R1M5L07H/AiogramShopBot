# TODO: Security & Architecture Findings

**Created:** 2025-11-13
**Source:** Code review during dialpad feature finalization
**Priority:** High (Security issues are critical)

## 🔴 Critical Security Issues

### 1. Webhook Secret Token Bypass Vulnerability

**Location:** `bot.py:102` and `utils/config_validator.py:108`

**Issue:**
- Webhook accepts any call when `WEBHOOK_SECRET_TOKEN` is missing
- Validator defaults to `DEPLOYMENT_MODE='POLLING'`
- Handler only compares incoming header to `None`
- Attacker can hit `/webhook/...` without secret and inject arbitrary updates

**Fix Required:**
- Force `DEPLOYMENT_MODE` to `WEBHOOK` for FastAPI deployments
- Fail-fast when secret/env is absent
- Reject requests where `X-Telegram-Bot-Api-Secret-Token` is missing

**Impact:** High - Allows unauthorized access to webhook endpoint

---

### 2. Payment Webhook Signature Bypass

**Location:** `processing/processing.py:20-33`

**Issue:**
- `__security_check` explicitly returns `True` when `X-Signature` header is absent
- Anyone can post unsigned payment payloads to `/cryptoprocessing/event`
- Can mark invoices or deposits as paid without authorization

**Fix Required:**
- Treat missing header as 403 Forbidden
- Only compute HMAC when header exists
- Add timing-safe comparison using raw body exactly as sent by provider
- Never allow missing signature to pass validation

**Impact:** Critical - Allows unauthorized payment manipulation

---

## 🟡 Architecture & Stability Issues

### 3. Destructive Auto-Migration on Schema Drift

**Location:** `db.py:133-144`

**Issue:**
- On startup, if any table check fails, `create_db_and_tables` drops ALL tables and recreates them
- Single missing table (e.g., schema drift in production) would wipe customer data
- No backup or migration strategy

**Fix Required:**
- Replace with proper migrations (Alembic)
- OR at minimum: Remove automatic `drop_all()`
- Log inconsistency and abort instead of destroying data
- Add pre-flight checks before destructive operations

**Impact:** High - Risk of data loss in production

---

### 4. Runtime Environment Enum Comparison Bug

**Location:** `config.py:146-149`

**Issue:**
- `RUNTIME_ENVIRONMENT` is a `RuntimeEnvironment` enum
- Code compares it to string `"dev"` instead of enum value
- Condition never becomes True
- Log retention always falls back to "prod" default (5 days) even in DEV/TEST

**Fix Required:**
```python
# Current (broken):
if RUNTIME_ENVIRONMENT == "dev":
    return DATA_RETENTION_DAYS

# Fixed:
if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
    return DATA_RETENTION_DAYS
```

**Impact:** Medium - Incorrect configuration behavior

---

### 5. N+1 Query in Purchase History

**Location:** `services/user.py:92-126`

**Issue:**
- "Batch load" logic still performs multiple sequential queries
- `BuyItemRepository.get_single_by_buy_id` and `ItemRepository.get_by_id` inside loops
- N+1 pattern will bog down history views as data grows

**Fix Required:**
- Fetch all buy items and items in bulk using `IN (...)` queries
- Map results before building keyboard
- Use eager loading or join queries

**Impact:** Medium - Performance degradation with scale

---

## Implementation Priority

1. **Immediate (Before next production deploy):**
   - Fix #1: Webhook Secret Token validation
   - Fix #2: Payment signature bypass

2. **High Priority (Next sprint):**
   - Fix #3: Replace destructive auto-migrate
   - Fix #4: Runtime environment enum comparison

3. **Medium Priority (Technical debt):**
   - Fix #5: N+1 query optimization

---

## Notes

- Issues #1 and #2 are blocking security vulnerabilities
- Issue #3 could cause catastrophic data loss
- Issues #4 and #5 are bugs but not security-critical
- All issues exist in codebase prior to dialpad feature
- None of these issues were introduced by dialpad implementation