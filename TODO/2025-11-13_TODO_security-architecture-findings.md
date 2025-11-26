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

## Automated Security Review (2025-11-25)

**Branches Reviewed:**
- `refactor/checkout-message-tier-display`
- `2025-11-22_admin-notification-new-user`

### 🔴 Critical Security Issues

### 13. HTML Injection in Invoice Formatter

**Location:** `services/invoice_formatter.py` (multiple locations)

**Issue:**
- Line 34-50: `private_data` rendered without escaping (direct HTML or wrapped in `<code>`/`<a>`)
- Line 79-137: Item names written to HTML without escaping for non-tiered items
- Line 843-846: Raw shipping addresses appended to admin messages
- Compromised vendor/DB records or malicious product names can inject HTML/scripts
- Affects all invoice views, checkout screens, and admin panels

**Fix Required:**
- Apply `safe_html()` to all user-controllable fields before embedding
- Validate URLs in `private_data` links (whitelist protocols: `https://`, `http://`)
- Escape shipping addresses before interpolation
- Review all `_format_*` methods for injection points

**Impact:** High - Stored XSS affecting users and admins

---

### 14. PII Leakage in Production Logs

**Location:** Multiple files

**Issue:**
- `handlers/user/shipping_handlers.py:23` - Logs first 100 chars of `web_app_data` payload (contains postal addresses)
- `bot.py:182-200` and `run.py:145-169` - Logs entire incoming updates and first 30 chars of every message/callback at DEBUG/WARNING levels
- User chats, addresses, callback payloads stored permanently in plaintext logs
- GDPR compliance violation

**Fix Required:**
- Gate shipping handler logging behind debug flag or remove entirely
- Drop update/message logging statements in production
- Mask PII fields before logging (redact or hash)
- Review log retention policy

**Impact:** High - Privacy compliance violation, data breach risk

---

### 15. Database Password Exposure in Logs

**Location:** `db.py:49-52` and `db.py:136`

**Issue:**
- Emits presence and length of `DB_PASS` at CRITICAL level when SQLCipher enabled
- Password interpolated directly into PRAGMA string
- Secrets may leak in log files or tracebacks

**Fix Required:**
- Remove all DB password logging statements
- Use parameterized PRAGMA calls (prevent password from appearing in process memory dumps)
- Review all `logging.*` calls for secret exposure

**Impact:** High - Credential exposure risk

---

## 🟡 Architecture & Stability Issues

### 16. Invoice Formatter God Class

**Location:** `services/invoice_formatter.py:20`

**Issue:**
- >1,100 lines mixing admin headers, cancellations, checkout, notifications
- Sprawling static API becoming untestable
- Drives in-function imports throughout services
- Single point of failure for all message formatting

**Fix Required:**
- Split into cohesive formatters (CheckoutFormatter, AdminNotificationFormatter, ShippingFormatter)
- Use strategy pattern per context
- Reduce cognitive complexity

**Impact:** Medium - Maintainability and testability

---

### 17. Dual Encryption Storage Architecture

**Location:** `services/encryption_wrapper.py` and `services/shipping.py`

**Issue:**
- Two parallel implementations for shipping address encryption
- `encryption_wrapper.py` writes to `orders.encrypted_payload`
- `services/shipping.py` writes to `shipping_addresses` table
- Models: `models/order.py:30-35` and `models/shipping_address.py:7-26`
- Maintaining dual storage invites data drift and bugs

**Fix Required:**
- Dedicate single service/table for address storage
- Deprecate redundant implementation
- Migrate existing data to unified storage

**Impact:** Medium - Data consistency risk

---

### 18. N+1 Query in Cart Price Tier Fetching

**Location:** `services/cart.py:657`

**Issue:**
- `PriceTierRepository.get_by_subcategory` called inside cart loop for every tiered item
- Creates N+1 query pattern
- Extra latency proportional to cart size

**Fix Required:**
- Prefetch all tiers for cart's `subcategory_ids` before loop
- Build local tier map
- Single batch query

**Impact:** Medium - Performance degradation with cart size

---

### 19. N+1 Query in Purchase Notifications

**Location:** `services/notification.py:129-158`

**Issue:**
- Fetches price, category, subcategory sequentially per cart item
- Runs inside webhook handler
- N+1 query storm for every purchase notification

**Fix Required:**
- Batch-load entities once per order
- Extend repositories to return joined DTOs
- Keep webhook latency predictable

**Impact:** Medium - Webhook handler performance

---

### 20. Float Precision in Currency Calculations

**Location:** `services/cart.py:706-754` and invoice formatter

**Issue:**
- Uses binary floats for currency math (`line_total = price * quantity`)
- Rounding drift between `total_savings`, `subtotal`, and stored order totals
- Will surface in invoices as inconsistencies

**Fix Required:**
- Use `Decimal` for all currency calculations
- Centralize rounding rules
- Ensure consistency across checkout, payment, invoices

**Impact:** Medium - Financial calculation accuracy

---

### 21. Redis Memory Leak (Missing TTL)

**Location:** `middleware/throttling_middleware.py:83-125`

**Issue:**
- Never expires Redis hashes created for rate limiting
- Every user interaction leaves permanent key
- `EXCEEDED_COUNT` grows without bound
- Unbounded Redis memory growth

**Fix Required:**
- Set TTL based on rate limit window
- Clamp counters to prevent indefinite accumulation
- Add Redis memory monitoring

**Impact:** Medium - Resource exhaustion over time

---

## 🔵 User Experience & Best Practices

### 22. Telegram Message Size Limit Risk

**Location:** `services/invoice_formatter.py:955-1040`

**Issue:**
- Builds single mega-message with tier breakdowns, positions, totals, savings
- Larger carts hit Telegram's 4,096 character limit
- Inline actions won't display when message truncated

**Fix Required:**
- Split into multiple messages (tier table + invoice summary)
- Truncate with "Show more" deep link for large carts
- Test with 50+ item carts

**Impact:** Medium - UX degradation for large orders

---

### 23. Hardcoded German Strings in Formatter

**Location:** `services/invoice_formatter.py:873-885`

**Issue:**
- Hardcodes German strings like "Stück" instead of using `Localizator`
- Multi-language bots show mixed languages in prominent upsell section
- Inconsistent with localization best practices

**Fix Required:**
- Pull all unit labels and text from localization files
- Remove hardcoded strings
- Test with English locale

**Impact:** Low - Localization consistency

---

### 24. Missing Alignment Preservation in Telegram

**Location:** `services/invoice_formatter.py:869-913`

**Issue:**
- Relies on variable-width spaces for column alignment
- Telegram collapses repeat spaces outside `<code>`/`<pre>`
- Tier tables appear misaligned on clients

**Fix Required:**
- Wrap tier table in `<pre>` or `<code>` tags
- Preserves alignment across all clients
- Keeps CTA lines readable

**Impact:** Low - Visual presentation

---

### 25. Admin Notification Never Fires for New Users (FIXED in PR #66)

**Location:** `run.py:58-78`

**Issue:**
- Ignores boolean returned by `UserService.create_if_not_exist`
- `NotificationService.notify_admin_new_user` never triggered at `/start` entry point
- User already in DB by time filters run
- Admins not alerted about first-time visitors

**Fix Applied (PR #66):**
- ✅ Implemented `notify_new_user_registration()` in NotificationService
- ✅ Integrated into `UserService.create_if_not_exist()`
- ✅ Configurable via `NOTIFY_ADMINS_NEW_USER` env var
- ✅ Uses `safe_html()` for security

**Status:** ✅ Fixed and merged

---

### 26. Sequential Admin Broadcasts Block Webhook

**Location:** `services/notification.py:43-52`

**Issue:**
- Sends admin messages sequentially for each `ADMIN_ID_LIST` entry
- Webhook handlers block while Telegram ACKs each send
- Multi-admin broadcasts slow message processing
- Can cause Telegram to retry updates

**Fix Required:**
- Use `asyncio.gather` for parallel sends
- OR use background queue for admin notifications
- Don't block webhook handlers

**Impact:** Low - Webhook handler latency

---

## Updated Implementation Priority

1. **Immediate (Before next production deploy):**
   - Fix #1: Webhook Secret Token validation
   - Fix #2: Payment signature bypass
   - **Fix #13: HTML Injection in invoice formatter**
   - **Fix #14: PII leakage in logs**
   - **Fix #15: Database password in logs** ← **FIXING NOW**
   - ✅ Fix #6: CSV Injection (COMPLETED)
   - ✅ Fix #7: Refund Data Integrity (COMPLETED)
   - ✅ Fix #25: Admin new-user notification (COMPLETED - PR #66)

2. **High Priority (Next sprint):**
   - Fix #3: Replace destructive auto-migrate
   - Fix #4: Runtime environment enum comparison
   - Fix #9: SQL aggregation for analytics
   - **Fix #16: Split invoice formatter god class**
   - **Fix #17: Unify encryption storage**
   - **Fix #20: Use Decimal for currency**

3. **Medium Priority (Technical debt):**
   - Fix #5: N+1 query optimization (user purchase history)
   - Fix #8: N+1 query optimization (analytics creation)
   - Fix #10: SQLite-specific code removal
   - Fix #11: Shipping address validation
   - Fix #12: User-specific localization
   - **Fix #18: N+1 query in cart tiers**
   - **Fix #19: N+1 query in notifications**
   - **Fix #21: Redis TTL for rate limiting**
   - **Fix #22: Message size limit handling**

4. **Low Priority (Nice to have):**
   - **Fix #23: Remove hardcoded German strings**
   - **Fix #24: Fix tier table alignment**
   - **Fix #26: Parallel admin broadcasts**

---

## Notes

- Issues #1 and #2 are blocking security vulnerabilities
- Issue #3 could cause catastrophic data loss
- **Issues #13, #14, #15 are new critical security findings requiring immediate attention**
- Issues #6 and #7 were security issues in Analytics v2, now fixed
- Issues #8, #9, #10 are performance/portability issues, not security-critical
- All pre-existing issues (#1-#5) exist in codebase prior to dialpad feature
- Analytics v2 issues (#6-#10) identified and partially fixed during feature development
- Automated review (2025-11-14) confirmed no new security issues in tiered shipping feature
- **Automated review (2025-11-25) identified 14 new issues across security, architecture, and UX categories**
- **Issue #25 fixed and merged in PR #66 (2025-11-25)**
