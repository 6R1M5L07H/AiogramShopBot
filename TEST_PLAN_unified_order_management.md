# Test Plan: Unified Order Management Refactoring

**Branch:** `feature/unify-order-management`
**Date:** 2025-11-05
**Goal:** Verify unified OrderManagementService works correctly for both Admin and User

---

## Pre-Test Setup

### 1. Environment Preparation
- [x] Start Bot: `python run.py`
- [x] Start Redis: `docker-compose -f docker-compose.dev.yml up -d`
- [x] Verify bot is running without errors
- [x] Check logs for any import errors

### 2. Test Data Requirements
- [ ] At least 20 orders in database (for pagination testing)
- [ ] Orders with different statuses:
  - [ ] PENDING_PAYMENT
  - [ ] PAID_AWAITING_SHIPMENT (at least 3)
  - [ ] SHIPPED (at least 3)
  - [ ] PAID (digital only, at least 2)
  - [ ] CANCELLED_BY_USER (at least 2)
  - [ ] CANCELLED_BY_ADMIN (at least 1)
  - [ ] TIMEOUT (at least 1)
- [ ] Test User 1: Has 5+ orders
- [ ] Test User 2: Has 0 orders (empty state)
- [ ] Admin User: Can see all orders

---

## Part 1: User Order History Tests

### 3. User Order List - Basic Display
**Navigation:** My Profile → Order History

**Expected Behavior:**
- [ ] 3.1 Order list shows with "All Orders" filter by default
- [ ] 3.2 Orders displayed in single-column layout
- [ ] 3.3 Each order shows: `[EMOJI] DD.MM • SHORT_ID • Status`
- [ ] 3.4 **NEW: Status emojis are visible** (⏳ 📝 ✅ 📦 🚚 ❌ etc.)
- [ ] 3.5 Orders sorted by date (newest first)
- [ ] 3.6 "Change Filter" button at bottom
- [ ] 3.7 "Back" button returns to My Profile

### 4. User Order List - Emojis Verification
**Focus:** Verify consistent emoji mapping

**Expected Emojis:**
- [ ] 4.1 ⏳ PENDING_PAYMENT
- [ ] 4.2 📝 PENDING_PAYMENT_AND_ADDRESS
- [ ] 4.3 ⚠️ PENDING_PAYMENT_PARTIAL
- [ ] 4.4 ✅ PAID
- [ ] 4.5 📦 PAID_AWAITING_SHIPMENT
- [ ] 4.6 🚚 SHIPPED
- [ ] 4.7 ❌ CANCELLED_BY_USER
- [ ] 4.8 🚫 CANCELLED_BY_ADMIN
- [ ] 4.9 ⛔ CANCELLED_BY_SYSTEM
- [ ] 4.10 ⏰ TIMEOUT

### 5. User Order List - Filters
**Test each filter:**

- [ ] 5.1 **All Orders Filter:**
  - Click "Change Filter" → Select "All Orders"
  - Shows: PAID + SHIPPED + all CANCELLED
  - Does NOT show: PENDING_PAYMENT orders

- [ ] 5.2 **Completed Filter:**
  - Click "Change Filter" → Select "Completed"
  - Shows only: PAID + SHIPPED orders
  - Count matches expected

- [ ] 5.3 **Cancelled Filter:**
  - Click "Change Filter" → Select "Cancelled"
  - Shows only: CANCELLED_BY_USER + CANCELLED_BY_ADMIN + CANCELLED_BY_SYSTEM + TIMEOUT
  - Count matches expected

### 6. User Order List - Pagination
**Prerequisites:** User has 15+ orders

- [ ] 6.1 First page shows max 8 orders (config.PAGE_ENTRIES)
- [ ] 6.2 "Weiter ▶️" button visible
- [ ] 6.3 Click "Weiter" → Shows next page
- [ ] 6.4 "◀️ Zurück" button visible on page 2
- [ ] 6.5 Click "Zurück" → Returns to page 1
- [ ] 6.6 Filter preserved during pagination

### 7. User Order Detail View
**Navigate:** Order List → Click any order

**Expected Behavior:**
- [ ] 7.1 Shows complete order invoice
- [ ] 7.2 Invoice number displayed (INV-2025-XXXXXX)
- [ ] 7.3 Order status with timestamps
- [ ] 7.4 Items listed (digital + physical separated)
- [ ] 7.5 Subtotal, shipping cost, total displayed
- [ ] 7.6 **No private_data visible** (user mode)
- [ ] 7.7 Shipping address shown (if exists, encrypted notice)
- [ ] 7.8 Back button returns to order list with **filter preserved**

### 8. User Order Detail - Ownership Security
**Test unauthorized access:**

- [ ] 8.1 User A logged in
- [ ] 8.2 Note order ID from User B (different user)
- [ ] 8.3 Attempt to view User B's order (via callback manipulation or direct access)
- [ ] 8.4 **Expected:** Error message "Order not found"
- [ ] 8.5 **Expected:** User A CANNOT see User B's order (security check)

### 9. User Empty State
**Prerequisites:** User with 0 orders

- [ ] 9.1 Navigate to Order History
- [ ] 9.2 Shows "No orders found" message
- [ ] 9.3 "Change Filter" and "Back" buttons still visible
- [ ] 9.4 No errors or crashes

---

## Part 2: Admin Order Management Tests

### 10. Admin Order List - Basic Display
**Navigation:** Admin Menu → Order Management

**Expected Behavior:**
- [ ] 10.1 Order list shows with "Requires Action" filter by default
- [ ] 10.2 Shows only PAID_AWAITING_SHIPMENT orders initially
- [ ] 10.3 Orders displayed in single-column layout
- [ ] 10.4 Each order shows: `[EMOJI] DD.MM • SHORT_ID • Status`
- [ ] 10.5 **Emojis match user's emojis** (consistency check)
- [ ] 10.6 Orders sorted by date (newest first)
- [ ] 10.7 "Change Filter" button at bottom
- [ ] 10.8 "Back" button returns to Admin Menu

### 11. Admin Order List - Emojis Consistency
**Focus:** Verify emojis IDENTICAL to user view

- [ ] 11.1 Compare admin emoji for PAID_AWAITING_SHIPMENT (📦) with user
- [ ] 11.2 Compare admin emoji for SHIPPED (🚚) with user
- [ ] 11.3 Compare admin emoji for CANCELLED_BY_USER (❌) with user
- [ ] 11.4 Compare admin emoji for PAID (✅) with user
- [ ] 11.5 **All emojis MUST be identical between admin and user**

### 12. Admin Order List - Filters
**Test all admin filters:**

- [ ] 12.1 **Requires Action Filter (Default):**
  - Shows only: PAID_AWAITING_SHIPMENT
  - Count matches expected

- [ ] 12.2 **All Orders Filter:**
  - Click "Change Filter" → Select "All Orders"
  - Shows: ALL orders regardless of status
  - Count matches total orders in database

- [ ] 12.3 **Active Filter:**
  - Click "Change Filter" → Select "Active"
  - Shows: PENDING_PAYMENT + PENDING_PAYMENT_AND_ADDRESS + PENDING_PAYMENT_PARTIAL + PAID_AWAITING_SHIPMENT
  - Does NOT show: PAID (digital complete)

- [ ] 12.4 **Completed Filter:**
  - Shows: PAID + SHIPPED
  - Count matches expected

- [ ] 12.5 **Cancelled Filter:**
  - Shows: CANCELLED_BY_USER + CANCELLED_BY_ADMIN + CANCELLED_BY_SYSTEM + TIMEOUT
  - Count matches expected

### 13. Admin Order List - Pagination
**Prerequisites:** Database has 25+ orders, filter shows 15+ results

- [ ] 13.1 First page shows max 8 orders
- [ ] 13.2 "Weiter ▶️" button visible
- [ ] 13.3 Pagination info button shows "Page X/Y"
- [ ] 13.4 Click "Weiter" → Shows next page
- [ ] 13.5 "◀️ Zurück" button visible on page 2
- [ ] 13.6 Click "Zurück" → Returns to page 1
- [ ] 13.7 Filter preserved during pagination

### 14. Admin Order Detail View
**Navigate:** Order List → Click any order

**Expected Behavior:**
- [ ] 14.1 Shows complete order invoice
- [ ] 14.2 Invoice number displayed
- [ ] 14.3 User info displayed (username + Telegram ID)
- [ ] 14.4 Order status with timestamps
- [ ] 14.5 Items listed (digital + physical separated)
- [ ] 14.6 **Private_data visible** (admin mode)
- [ ] 14.7 Subtotal, shipping cost, total displayed
- [ ] 14.8 Shipping address shown (if exists, decrypted)
- [ ] 14.9 **Payment History section visible** (wallet, crypto details)
- [ ] 14.10 Context-aware action buttons (Mark as Shipped, Cancel Order)
- [ ] 14.11 Back button returns to order list with **filter + page preserved**

### 15. Admin Order Detail - Payment History
**Focus:** Admin-specific payment details

- [ ] 15.1 Payment History section present
- [ ] 15.2 Shows: Order created timestamp
- [ ] 15.3 Shows: Payment received timestamp
- [ ] 15.4 Shows: Payment method (Wallet / Crypto / Mixed)
- [ ] 15.5 Shows: Wallet amount used (if any)
- [ ] 15.6 Shows: Crypto payment details:
  - [ ] Currency (BTC, ETH, etc.)
  - [ ] Amount paid
  - [ ] KryptoExpress transaction ID
  - [ ] KryptoExpress order ID
  - [ ] Payment address
  - [ ] Confirmation timestamp
- [ ] 15.7 Shows: Underpayment retry count (if any)
- [ ] 15.8 Shows: Late payment penalty (if applied)

### 16. Admin Order Detail - Action Buttons
**Test context-aware buttons:**

- [ ] 16.1 **PAID_AWAITING_SHIPMENT order:**
  - Shows: "Mark as Shipped" button
  - Shows: "Cancel Order" button
  - Click "Mark as Shipped" → Works correctly

- [ ] 16.2 **SHIPPED order:**
  - Does NOT show: "Mark as Shipped"
  - Does NOT show: "Cancel Order"
  - Only shows: "Back" button

- [ ] 16.3 **PAID order (digital only):**
  - Does NOT show: "Mark as Shipped"
  - Does NOT show: "Cancel Order" (items already delivered)

- [ ] 16.4 **PENDING_PAYMENT order:**
  - Does NOT show: "Mark as Shipped"
  - Shows: "Cancel Order" button

- [ ] 16.5 **CANCELLED order:**
  - No action buttons shown

### 17. Admin All Users Access
**Verify admin sees ALL users' orders:**

- [ ] 17.1 Create order as User A
- [ ] 17.2 Create order as User B
- [ ] 17.3 Login as Admin
- [ ] 17.4 Navigate to Order Management → All Orders filter
- [ ] 17.5 **Expected:** Both User A and User B orders visible
- [ ] 17.6 **Expected:** Orders from ALL users in database visible

### 18. Admin Empty States
**Test edge cases:**

- [ ] 18.1 Filter with 0 results (e.g., "Requires Action" when no PAID_AWAITING_SHIPMENT)
- [ ] 18.2 Shows "No orders found"
- [ ] 18.3 "Change Filter" and "Back" buttons still visible
- [ ] 18.4 No errors or crashes

---

## Part 3: Consistency Verification

### 19. UI Layout Consistency
**Compare admin vs user side-by-side:**

- [ ] 19.1 Order list button format IDENTICAL
- [ ] 19.2 Date format IDENTICAL (DD.MM)
- [ ] 19.3 Invoice short format IDENTICAL (last 6 chars)
- [ ] 19.4 Status text IDENTICAL
- [ ] 19.5 Pagination style IDENTICAL
- [ ] 19.6 Filter change button IDENTICAL
- [ ] 19.7 Only difference: Admin sees username/ID, user doesn't

### 20. Emoji Mapping Consistency
**Verify STATUS_EMOJI_MAP used consistently:**

- [ ] 20.1 Open same order as admin and user (different accounts)
- [ ] 20.2 Compare emoji shown for same status
- [ ] 20.3 **Must be IDENTICAL**
- [ ] 20.4 Repeat for 3 different order statuses
- [ ] 20.5 All emojis match

### 21. Filter Logic Consistency
**Verify filter behavior:**

- [ ] 21.1 User "All Orders" excludes PENDING_PAYMENT (correct)
- [ ] 21.2 Admin "All Orders" includes PENDING_PAYMENT (correct)
- [ ] 21.3 Both "Completed" filters show PAID + SHIPPED
- [ ] 21.4 Both "Cancelled" filters show all cancelled states
- [ ] 21.5 Filter names localized correctly (DE/EN)

### 22. Navigation Flow Consistency
**Test navigation state preservation:**

- [ ] 22.1 User: Filter → List → Detail → Back → Correct filter restored
- [ ] 22.2 Admin: Filter → List → Detail → Back → Correct filter restored
- [ ] 22.3 User: Page 2 → Detail → Back → Returns to page 2
- [ ] 22.4 Admin: Page 2 → Detail → Back → Returns to page 2
- [ ] 22.5 Both preserve filter + page state identically

---

## Part 4: Edge Cases & Error Handling

### 23. Order Not Found
- [ ] 23.1 User: Try to access non-existent order ID
- [ ] 23.2 Shows: "Order not found" error
- [ ] 23.3 Admin: Try to access non-existent order ID
- [ ] 23.4 Shows: "Order not found" error
- [ ] 23.5 No crashes or stack traces visible

### 24. Database Edge Cases
- [ ] 24.1 Order without invoice → Shows fallback ORDER-YYYY-XXXXXX
- [ ] 24.2 Order without user → Handles gracefully
- [ ] 24.3 Order with missing shipping address → No errors
- [ ] 24.4 Order with decryption failed address → Shows notice (user), shows error (admin)

### 25. Pagination Edge Cases
- [ ] 25.1 Exactly 8 orders (1 page) → No pagination buttons
- [ ] 25.2 Exactly 9 orders (2 pages) → Pagination appears
- [ ] 25.3 Last page with < 8 orders → Displays correctly
- [ ] 25.4 Navigate beyond max page → Handled gracefully

### 26. Filter Edge Cases
- [ ] 26.1 Switch filter while on page 2 → Resets to page 1
- [ ] 26.2 Filter with 0 results → Shows empty state
- [ ] 26.3 Rapid filter changes → No race conditions
- [ ] 26.4 Filter change preserves other callback data

---

## Part 5: Performance & Code Quality

### 27. N+1 Query Prevention
**Monitor database queries:**

- [ ] 27.1 Admin: View order list → Count SQL queries
- [ ] 27.2 **Expected:** Fixed number of queries (not proportional to order count)
- [ ] 27.3 User: View order list → Count SQL queries
- [ ] 27.4 **Expected:** Fixed number of queries
- [ ] 27.5 Eager loading working (user, invoices loaded in batch)

### 28. Code Reduction Verification
**Before/After comparison:**

- [ ] 28.1 `services/user.py`: Reduced by ~200 lines ✓
- [ ] 28.2 `handlers/admin/shipping_management.py`: Reduced by ~110 lines ✓
- [ ] 28.3 `repositories/order.py`: Redundant methods deleted ✓
- [ ] 28.4 Total reduction: ~730 lines ✓
- [ ] 28.5 New unified service: 420 lines ✓
- [ ] 28.6 **Net reduction: -310 lines of duplicated logic**

### 29. Import & Syntax Check
- [ ] 29.1 No import errors in logs
- [ ] 29.2 `python -m py_compile services/order_management.py` → Success
- [ ] 29.3 `python -m py_compile services/user.py` → Success
- [ ] 29.4 `python -m py_compile handlers/admin/shipping_management.py` → Success
- [ ] 29.5 `python -m py_compile repositories/order.py` → Success

### 30. Localization Keys
**Verify all l10n keys exist:**

- [ ] 30.1 `order_list_title` (USER, ADMIN)
- [ ] 30.2 `order_filter_current` (USER, ADMIN)
- [ ] 30.3 `order_no_orders` (USER, ADMIN)
- [ ] 30.4 `order_filter_change_button` (USER, ADMIN)
- [ ] 30.5 `order_status_*` for all OrderStatus values (COMMON)
- [ ] 30.6 No missing key errors in logs

---

## Part 6: Regression Tests

### 31. Existing Admin Features Still Work
**Verify nothing broke:**

- [ ] 31.1 Admin: Mark as Shipped functionality works
- [ ] 31.2 Admin: Cancel Order with custom reason works
- [ ] 31.3 Admin: Filter selection UI works
- [ ] 31.4 Admin: Payment History display works
- [ ] 31.5 Admin: Shipping address decryption works

### 32. Existing User Features Still Work
- [ ] 32.1 User: Order History accessible from My Profile
- [ ] 32.2 User: Filter selection works
- [ ] 32.3 User: Order detail view works
- [ ] 32.4 User: Ownership check prevents unauthorized access
- [ ] 32.5 User: Shipping address encryption notice shown

### 33. Unrelated Features Unaffected
**Sanity checks:**

- [ ] 33.1 User: Cart functionality works
- [ ] 33.2 User: Checkout flow works
- [ ] 33.3 User: Payment creation works
- [ ] 33.4 Admin: User Management works
- [ ] 33.5 Admin: Inventory Management works

---

## Success Criteria

### Must Pass (Blockers):
1. ✅ All User Order History tests pass (Tests 3-9)
2. ✅ All Admin Order Management tests pass (Tests 10-18)
3. ✅ Emojis consistent between admin and user (Tests 11, 20)
4. ✅ No security vulnerabilities (Test 8)
5. ✅ No crashes or errors in logs
6. ✅ Code reduction verified (-310 lines net)

### Should Pass (High Priority):
7. ✅ UI consistency verified (Test 19)
8. ✅ Navigation state preservation works (Test 22)
9. ✅ All edge cases handled gracefully (Tests 23-26)
10. ✅ Performance acceptable (N+1 queries prevented, Test 27)

### Nice to Have (Low Priority):
11. ✅ All localization keys present (Test 30)
12. ✅ Regression tests pass (Tests 31-33)

---

## Test Execution Log

### Tester: _________________
### Date: _________________
### Build/Commit: `81aaad3`

| Test # | Status | Notes |
|--------|--------|-------|
| 3.1    | ⬜     |       |
| 3.2    | ⬜     |       |
| ...    | ⬜     |       |

**Overall Result:** ⬜ PASS / ⬜ FAIL / ⬜ BLOCKED

**Issues Found:**
1.
2.
3.

**Recommendations:**
1.
2.
