# Manual Test Guide: Shipping Management Refactoring

**Test Target:** `handlers/admin/shipping_management.py`
**Refactoring:** Move business logic from handler to `services/shipping.py`
**Risk Level:** MEDIUM (Admin-only feature, but critical for operations)

---

## Pre-Refactoring Test (Baseline)

Run these tests **BEFORE** the refactoring to establish baseline behavior.

###   Test 1: View Pending Shipments (Empty State)

**Prerequisites:**
- No orders in PENDING_SHIPMENT status
- You are logged in as admin

**Steps:**
1. Open bot
2. Click "Admin Menu" button
3. Click "Shipping Management" button
4. Observe the message

**Expected Result:**
-   Message shows "No orders awaiting shipment" or similar (DE: "Keine Bestellungen warten auf Versand")
-   "Back" button is visible
-   No errors displayed

---

###   Test 2: View Pending Shipments (With Orders)

**Prerequisites:**
- At least 1 order in PENDING_SHIPMENT status
- You are logged in as admin

**Setup (if needed):**
1. Create test order as user (with physical items)
2. Pay for order
3. Order should be in PENDING_SHIPMENT status

**Steps:**
1. Open bot
2. Click "Admin Menu" → "Shipping Management"
3. Observe the list of orders

**Expected Result:**
-   List shows all pending shipments
-   Each order shows:
  - Invoice number (e.g., INV-12345)
  - Username (e.g., @testuser)
  - Total amount (e.g., €50.00)
-   Each order has "View Details" button
-   "Back" button is visible
-   No errors displayed

**Screenshot:** Take a screenshot of this screen for comparison after refactoring

---

###   Test 3: View Order Details

**Prerequisites:**
- At least 1 order in PENDING_SHIPMENT status

**Steps:**
1. Admin Menu → Shipping Management
2. Click "View Details" on any order
3. Observe the order details screen

**Expected Result:**
-   Shows complete order information:
  - Invoice number
  - Order status (PENDING_SHIPMENT)
  - Username and Telegram ID
  - Items list (with quantities and prices)
  - Shipping address (full address displayed)
  - Payment method (crypto/wallet)
  - Total amount
  - Timestamps (created, payment received)
-   Buttons visible:
  - "Mark as Shipped" button
  - "View Invoice" button (if applicable)
  - "Back to List" button
-   No errors displayed

**Screenshot:** Take a screenshot for comparison

---

###   Test 4: Mark Order as Shipped

**Prerequisites:**
- At least 1 order in PENDING_SHIPMENT status
- You know the order owner's Telegram ID

**Steps:**
1. Admin Menu → Shipping Management
2. Click "View Details" on an order
3. Click "Mark as Shipped" button
4. Observe confirmation

**Expected Result:**
-   Success message appears (e.g., "Order marked as shipped")
-   User receives notification about shipment
-   Order disappears from pending shipments list
-   Order status updated to SHIPPED in database
-   No errors displayed

**Verify User Side:**
1. Check user's Telegram (the one who placed the order)
2.   Should receive notification: "Your order [INV-XXX] has been shipped"

---

###   Test 5: Multiple Pending Orders

**Prerequisites:**
- At least 3 orders in PENDING_SHIPMENT status

**Steps:**
1. Admin Menu → Shipping Management
2. View list of all pending orders
3. Click through each order's details
4. Mark one order as shipped
5. Return to pending shipments list

**Expected Result:**
-   All 3+ orders displayed initially
-   Can navigate between order details
-   After marking one as shipped, list shows 2 remaining orders
-   Navigation works smoothly (no stuck states)
-   No errors during navigation

---

###   Test 6: Order with Digital Items Only

**Note:** This test is for edge case handling

**Prerequisites:**
- Create order with **only digital items** (no physical items)
- This order might not appear in shipping management (expected behavior)

**Steps:**
1. Admin Menu → Shipping Management
2. Check if digital-only order appears

**Expected Result:**
-   Digital-only orders should NOT appear in shipping list (no address needed)
-   Only orders with physical items should appear
-   No errors displayed

---

###   Test 7: Order with Mixed Items (Digital + Physical)

**Prerequisites:**
- Create order with both digital AND physical items

**Steps:**
1. Admin Menu → Shipping Management
2. Find the mixed order
3. Click "View Details"
4. Mark as shipped

**Expected Result:**
-   Order appears in shipping list (has physical items)
-   Details show both digital and physical items
-   Shipping address is present
-   Can mark as shipped successfully
-   User receives notification
-   No errors displayed

---

###   Test 8: Back Navigation

**Steps:**
1. Admin Menu → Shipping Management (List)
2. Click "View Details" on an order (Details screen)
3. Click "Back to List" button
4. Verify you're back at the list
5. Click "Back" button
6. Verify you're back at Admin Menu

**Expected Result:**
-   All navigation buttons work correctly
-   No stuck screens
-   No errors during navigation

---

###   Test 9: Concurrent Admin Access (Optional)

**Prerequisites:**
- Two admin accounts

**Steps:**
1. Admin 1: Open Shipping Management list
2. Admin 2: Open same list
3. Admin 1: Mark order as shipped
4. Admin 2: Refresh list (go back and re-enter)

**Expected Result:**
-   Admin 2 sees updated list (order removed)
-   No data inconsistency
-   No errors

---

###   Test 10: Error Handling - Non-Existent Order

**Steps:**
1. Admin Menu → Shipping Management
2. (Manually) try to access order that doesn't exist
   - This might require URL manipulation or callback modification
   - Or: Mark order as shipped, then try to access it again

**Expected Result:**
-   Graceful error message (not crash)
-   "Order not found" or similar message
-   Can navigate back to list

---

## Post-Refactoring Tests

After refactoring is complete, run **ALL tests above again** and verify:

  **Same behavior** - Everything works exactly as before
  **Same UI/UX** - Messages and buttons look identical
  **Same notifications** - Users receive same notifications
  **No new errors** - No new error messages or crashes
  **No performance degradation** - Responds as fast as before

---

## Additional Checks (Post-Refactoring)

### Check 1: Code Quality

```bash
# Run automated tests
pytest tests/admin/test_shipping_management.py -v

# Expected: All tests pass  
```

### Check 2: Import Check

Verify `handlers/admin/shipping_management.py` no longer imports repositories:

```bash
grep "from repositories" handlers/admin/shipping_management.py
```

**Expected:** No matches (or only comments)

### Check 3: Service Layer Created

```bash
ls -la services/shipping.py
```

**Expected:** File exists with ShippingService class

---

## Rollback Plan

If any test fails after refactoring:

```bash
# Revert the commit
git revert <commit-hash>

# Or reset to before refactoring
git reset --hard <commit-before-refactoring>
```

---

## Test Results Template

Copy this for your test report:

```markdown
## Test Results: Shipping Management Refactoring

**Date:** YYYY-MM-DD
**Tester:** [Your Name]
**Branch:** technical-debt
**Commit:** [commit hash]

### Pre-Refactoring Tests (Baseline)
- [ ] Test 1: Empty State - PASS / FAIL
- [ ] Test 2: With Orders - PASS / FAIL
- [ ] Test 3: Order Details - PASS / FAIL
- [ ] Test 4: Mark as Shipped - PASS / FAIL
- [ ] Test 5: Multiple Orders - PASS / FAIL
- [ ] Test 6: Digital Only - PASS / FAIL
- [ ] Test 7: Mixed Items - PASS / FAIL
- [ ] Test 8: Navigation - PASS / FAIL
- [ ] Test 9: Concurrent Access - PASS / FAIL (Optional)
- [ ] Test 10: Error Handling - PASS / FAIL

### Post-Refactoring Tests
- [ ] Test 1: Empty State - PASS / FAIL
- [ ] Test 2: With Orders - PASS / FAIL
- [ ] Test 3: Order Details - PASS / FAIL
- [ ] Test 4: Mark as Shipped - PASS / FAIL
- [ ] Test 5: Multiple Orders - PASS / FAIL
- [ ] Test 6: Digital Only - PASS / FAIL
- [ ] Test 7: Mixed Items - PASS / FAIL
- [ ] Test 8: Navigation - PASS / FAIL
- [ ] Test 9: Concurrent Access - PASS / FAIL (Optional)
- [ ] Test 10: Error Handling - PASS / FAIL

### Automated Tests
- [ ] pytest tests/admin/test_shipping_management.py - PASS / FAIL

### Overall Result
- [ ]   All tests passed - SAFE TO MERGE
- [ ]   Some tests failed - DO NOT MERGE (see details below)

**Notes:**
[Add any observations, issues, or comments here]
```

---

## Contact

If you find any issues during testing, document:
1. Which test failed
2. What was the expected behavior
3. What actually happened
4. Screenshots (if applicable)
5. Error messages (if any)

**Ready to test!**  
