# TODO: Security & Architecture Findings

**Created:** 2025-11-13
**Source:** Code review during dialpad feature finalization
**Priority:** High (Security issues are critical)

## Pre-Notes

Discuss every single finding before actually fixing it!


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

---

## 🟢 Fixed Issues (Analytics v2)

### 6. CSV Injection Vulnerability (FIXED)

**Location:** `services/analytics.py:261-300`

**Issue:**
- CSV generation used f-strings without escaping
- Category/subcategory names with `=`, `+`, `-`, `@` could execute formulas in Excel
- Example: Category name `=1+1` would execute as formula

**Fix Applied:**
- Replaced f-string concatenation with Python `csv` module
- Using `csv.QUOTE_ALL` to properly escape all fields
- Enum values converted to `.value` for clean export

**Status:** ✅ Fixed in current commit

---

### 7. Refund Data Integrity Issue (FIXED)

**Location:** `repositories/sales_record.py:352-404`

**Issue:**
- Refund marking used only `sale_date + category_name + subcategory_name`
- Could mark ALL sales of same category on same day as refunded
- Malicious user cancelling one order could corrupt entire day's analytics

**Fix Applied:**
- Added `order_hash` column to SalesRecord (SHA256 of `order_id + created_at`)
- Pseudonymized identifier maintains data minimization
- Refund updates now precisely target specific order's records

**Status:** ✅ Fixed in current commit

---

## 🟡 New Architecture Issues (Analytics v2)

### 8. N+1 Query in Sales Record Creation

**Location:** `services/analytics.py:93-131`

**Issue:**
- Each item fetches Category and Subcategory individually
- 20-item order = 40 database queries
- Expensive for large orders

**Fix Required:**
- Batch load categories and subcategories before loop
- Build lookup dictionaries
- Reduce to 2 queries regardless of order size

**Impact:** Medium - Performance issue for large orders

---

### 9. Memory Loading Instead of SQL Aggregation

**Location:** `repositories/sales_record.py:226-295`

**Issue:**
- Loads ALL sales for time range into memory
- Groups in Python instead of SQL GROUP BY
- 90-day reports block event loop
- Does not scale beyond 10,000 records

**Fix Required:**
- Move aggregation to SQL with GROUP BY
- Apply pagination in SQL, not Python
- Return only requested page from database

**Impact:** High - Scalability bottleneck

---

### 10. SQLite-Specific Distinct Count

**Location:** `repositories/sales_record.py:316-325`

**Issue:**
- Uses string concatenation for distinct count: `category + '|' + subcategory`
- Only works on SQLite
- Prevents migration to PostgreSQL/MySQL

**Fix Required:**
- Use `tuple_()` for DB-agnostic distinct count
- OR use subquery approach

**Impact:** Medium - Blocks database migration

---

## Implementation Priority

1. **Immediate (Before next production deploy):**
   - Fix #1: Webhook Secret Token validation
   - Fix #2: Payment signature bypass
   - ✅ Fix #6: CSV Injection (COMPLETED)
   - ✅ Fix #7: Refund Data Integrity (COMPLETED)

2. **High Priority (Next sprint):**
   - Fix #3: Replace destructive auto-migrate
   - Fix #4: Runtime environment enum comparison
   - Fix #9: SQL aggregation for analytics

3. **Medium Priority (Technical debt):**
   - Fix #5: N+1 query optimization (user purchase history)
   - Fix #8: N+1 query optimization (analytics creation)
   - Fix #10: SQLite-specific code removal

---

## 🔵 User Experience & Best Practices

### 11. Insufficient Shipping Address Validation

**Location:** `handlers/user/shipping_handlers.py:19-49`

**Issue:**
- Accepts any string >10 characters as valid shipping address
- No country-specific validation (postal codes, street format)
- Direct interpolation into confirmation message without safe_html
- Support burden due to incorrect/incomplete addresses

**Fix Required:**
- Implement country-specific address validation (street, postal code, city)
- Offer inline address suggestions via Telegram Bot API
- Apply safe_html before re-displaying user input in messages
- Consider structured address entry (separate fields)

**Impact:** Medium - User experience and support overhead

---

### 12. Missing User-Specific Localization

**Location:** `run.py:39-59`

**Issue:**
- Uses global bot language setting for all users
- Ignores `message.from_user.language_code` from Telegram
- Users with different language preferences see German-only content
- Reduces bot "nativeness" and increases support requests

**Fix Required:**
- Read user language from `message.from_user.language_code`
- Store language preference in user profile
- Apply per-user localization for menus, help, FAQs
- Fallback to bot default if user language not supported

**Impact:** Medium - User experience and internationalization

---

## Automated Security Review (2025-11-14)

**Branch:** `feature/tiered-pricing-shipping-upselling`

### Findings Summary:

**Critical Security Issues Confirmed:**
- ✅ Issue #2: Payment webhook signature bypass (`processing/processing.py:23-31`)
- ✅ Issue #1: Telegram webhook secret token bypass (`bot.py:170-174`, `utils/config_validator.py:108`)
- ✅ Issue #3: Destructive DB auto-reset (`db.py:133-144`)

**Architecture Issues Confirmed:**
- ✅ Issue #4: Runtime environment enum comparison bug (`config.py:143-149`)
- ✅ Issue #5: N+1 query in purchase history (`services/user.py:92-125`)

**New Issues Identified:**
- ⚠️ Issue #11: Insufficient shipping address validation
- ⚠️ Issue #12: Missing user-specific localization

**Verdict:** No new security vulnerabilities introduced by tiered shipping feature. All findings are pre-existing issues or UX improvements.

---

## Updated Implementation Priority

1. **Immediate (Before next production deploy):**
   - Fix #1: Webhook Secret Token validation
   - Fix #2: Payment signature bypass
   - ✅ Fix #6: CSV Injection (COMPLETED)
   - ✅ Fix #7: Refund Data Integrity (COMPLETED)

2. **High Priority (Next sprint):**
   - Fix #3: Replace destructive auto-migrate
   - Fix #4: Runtime environment enum comparison
   - Fix #9: SQL aggregation for analytics

3. **Medium Priority (Technical debt):**
   - Fix #5: N+1 query optimization (user purchase history)
   - Fix #8: N+1 query optimization (analytics creation)
   - Fix #10: SQLite-specific code removal
   - Fix #11: Shipping address validation
   - Fix #12: User-specific localization

---

## Notes

- Issues #1 and #2 are blocking security vulnerabilities
- Issue #3 could cause catastrophic data loss
- Issues #6 and #7 were security issues in Analytics v2, now fixed
- Issues #8, #9, #10 are performance/portability issues, not security-critical
- All pre-existing issues (#1-#5) exist in codebase prior to dialpad feature
- Analytics v2 issues (#6-#10) identified and partially fixed during feature development
- Automated review (2025-11-14) confirmed no new security issues in tiered shipping feature
