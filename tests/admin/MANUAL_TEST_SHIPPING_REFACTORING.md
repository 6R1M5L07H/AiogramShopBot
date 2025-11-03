# Manual Test: Shipping Management Refactoring

**Date:** 2025-11-02
**Branch:** feature/strike-system (or technical-debt)
**Tester:** [Your Name]
**Test System:** Development

---

## Test Accounts

- **Admin Account:** [Admin Telegram Username/ID]
- **User Account:** [User Telegram Username/ID]

---

## Preparation: Create Test Order

### Setup: Create Order with Physical Items

**Account:** User Account

- [ ] 1. Start bot
- [ ] 2. Browse categories and find physical item
- [ ] 3. Add item to cart
- [ ] 4. Start checkout
- [ ] 5. Enter shipping address (test address):
  ```
  Max Mustermann
  Musterstrasse 123
  12345 Musterstadt
  Germany
  ```
- [ ] 6. Select payment method (Crypto or Wallet)
- [ ] 7. Complete payment (simulate test payment)
- [ ] 8. **Note Invoice Number:** `INV-________`

**Expected Result:**
- Order created successfully
- Status: PAID_AWAITING_SHIPMENT
- User receives order confirmation

---

## Test 1: Empty State (No Pending Orders)

**Precondition:** No orders in PAID_AWAITING_SHIPMENT status

**Account:** Admin Account

- [ ] 1. Open bot
- [ ] 2. Click "Admin Menu"
- [ ] 3. Click "Shipping Management"

**Expected Result:**
- [ ] Message: "No orders awaiting shipment"
- [ ] "Back to Menu" button visible
- [ ] No crash, no error message

**Actual Result:**
```
[Describe what happened]
```

**Status:** PASS / FAIL

---

## Test 2: Display Order List (With Orders)

**Precondition:** At least 1 order from setup exists

**Account:** Admin Account

- [ ] 1. Admin Menu → Shipping Management

**Expected Result:**
- [ ] List shows at least 1 order
- [ ] Each line displays:
  - [ ] Icon
  - [ ] Date/Time (e.g. "02.11 14:30")
  - [ ] Invoice number (e.g. "INV-12345")
  - [ ] Username + ID (e.g. "@testuser (ID:123456789)")
  - [ ] Total price (e.g. "50.00€")
- [ ] "View Details" button per order
- [ ] "Back to Menu" button at the end

**Actual Result:**
```
[Describe what is displayed]
```

**Status:** PASS / FAIL

---

## Test 3: Display Order Details

**Account:** Admin Account

- [ ] 1. Open Shipping Management list
- [ ] 2. Click on an order ("View Details")

**Expected Result:**
- [ ] Header shows:
  - [ ] Invoice number
  - [ ] Username
  - [ ] User ID
- [ ] Items listed:
  - [ ] Digital items (if any): Under "Digital:"
  - [ ] Physical items: Under "Items to Ship:"
  - [ ] Quantity, description, price visible
- [ ] Shipping costs displayed (if > 0)
- [ ] Total price: `Total: XX.XX €`
- [ ] **Address data completely displayed:**
  ```
  Max Mustermann
  Musterstrasse 123
  12345 Musterstadt
  Germany
  ```
- [ ] Buttons visible:
  - [ ] "Mark as Shipped"
  - [ ] "Cancel Order"
  - [ ] "Back"

**Actual Result:**
```
[Describe the detail view]
```

**Status:** PASS / FAIL

---

## Test 4: Mark as Shipped (CRITICAL!)

**Account:** Admin Account (for action) + User Account (for notification)

### Part A: Admin Marks as Shipped

**Account:** Admin Account

- [ ] 1. Shipping Management → Select order
- [ ] 2. Click "Mark as Shipped"
- [ ] 3. **Confirmation appears?**
  - [ ] Text: "Mark order [INV-XXX] as shipped?"
  - [ ] "Confirm" button
  - [ ] "Cancel" button
- [ ] 4. Click "Confirm"

**Expected Result:**
- [ ] Success message: "Order [INV-XXX] marked as shipped"
- [ ] "Back to Menu" button

**Actual Result:**
```
[Describe what happened]
```

### Part B: User Receives Notification

**Account:** User Account (check Telegram chat!)

- [ ] 5. **Check user chat:** Was notification received?

**Expected Result:**
- [ ] User receives Telegram message:
  - [ ] Text contains: "Your order [INV-XXX] has been shipped"
  - [ ] No errors

**Actual Result:**
```
[Was notification received? Yes/No]
[Notification text:]
```

### Part C: Order Disappears from List

**Account:** Admin Account

- [ ] 6. Navigate back to "Shipping Management"
- [ ] 7. Reload list

**Expected Result:**
- [ ] Order is NO longer in the list
- [ ] If it was the last one: "No orders awaiting shipment"

**Actual Result:**
```
[Is order gone? Yes/No]
```

**Status:** PASS / FAIL

---

## Test 5: Navigation (Back Buttons)

**Account:** Admin Account

- [ ] 1. Admin Menu → Shipping Management (List)
- [ ] 2. Open Order Details
- [ ] 3. Click "Back" → Should return to List
- [ ] 4. Click "Back to Menu" → Should return to Admin Menu
- [ ] 5. Again "Shipping Management" → "Order Details" → "Mark as Shipped" → "Cancel"
- [ ] 6. Should return to Details

**Expected Result:**
- [ ] All back buttons work
- [ ] No "stuck screens"
- [ ] No duplicate messages

**Actual Result:**
```
[Describe navigation flow]
```

**Status:** PASS / FAIL

---

## Test 6: Error Handling - Non-Existent Order (NEW - Bug Fix!)

**Precondition:** An order that was just marked as shipped

**Account:** Admin Account

- [ ] 1. Open Shipping Management
- [ ] 2. Mark order as "Shipped"
- [ ] 3. **Browser/Telegram "Back" button** press (back to Details)
- [ ] 4. Try to click "Mark as Shipped" again

**Expected Result (AFTER Refactoring):**
- [ ] **Graceful error message:** "Order not found" or similar
- [ ] "Back to Menu" button works
- [ ] **NO CRASH!** (Previously: NoResultFound Exception)

**Actual Result:**
```
[What happens? Error message or crash?]
```

**Status:** PASS / FAIL

---

## Test 7: Cancel Order

**Precondition:** Create new order (see Setup)

**Account:** Admin Account

- [ ] 1. Shipping Management → Order Details
- [ ] 2. Click "Cancel Order"
- [ ] 3. Choose "Cancel without reason"
- [ ] 4. Confirm

**Expected Result:**
- [ ] Success message appears
- [ ] Order disappears from Shipping Management list
- [ ] User receives cancellation notification (check user chat!)
- [ ] Wallet balance was refunded (if wallet payment)

**Actual Result:**
```
[Describe what happened]
```

**Status:** PASS / FAIL

---

## Test 8: Mixed Order (Digital + Physical)

**Precondition:** Create order with both digital AND physical items

**Setup:**
- [ ] User Account: Buy 1x digital item + 1x physical item

**Account:** Admin Account

- [ ] 1. Shipping Management → Open Order Details

**Expected Result:**
- [ ] Two sections visible:
  - [ ] "Digital:" with digital items
  - [ ] "Items to Ship:" with physical items
- [ ] Address is displayed (because of physical items)
- [ ] Both item types correctly grouped

**Actual Result:**
```
[Describe display]
```

**Status:** PASS / FAIL

---

## Test 9: Multiple Pending Orders

**Precondition:** Create 3+ orders in PAID_AWAITING_SHIPMENT status

**Account:** Admin Account

- [ ] 1. Open Shipping Management
- [ ] 2. Go through all orders (open Details)
- [ ] 3. Mark one order as "Shipped"
- [ ] 4. Back to list

**Expected Result:**
- [ ] Initial: All 3+ orders displayed
- [ ] After marking: Only 2 orders left in list
- [ ] Details navigation works for all orders
- [ ] No confusion between orders

**Actual Result:**
```
[Describe multi-order handling]
```

**Status:** PASS / FAIL

---

## Test 10: Performance & Responsiveness

**Account:** Admin Account

- [ ] 1. Open Shipping Management with multiple orders
- [ ] 2. Switch between orders
- [ ] 3. Execute multiple actions quickly in succession

**Expected Result:**
- [ ] List loads quickly (< 2 seconds)
- [ ] Details load quickly
- [ ] No delayed updates
- [ ] No duplicate notifications

**Actual Result:**
```
[Describe performance]
```

**Status:** PASS / FAIL

---

## Summary

### Test Results

| Test | Status | Notes |
|------|--------|-------|
| Test 1: Empty State | | |
| Test 2: Display List | | |
| Test 3: Display Details | | |
| Test 4: Mark as Shipped | | **CRITICAL** |
| Test 5: Navigation | | |
| Test 6: Error Handling (Bug Fix) | | **NEW** |
| Test 7: Cancel Order | | |
| Test 8: Mixed Order | | |
| Test 9: Multiple Orders | | |
| Test 10: Performance | | |

### Overall Result

- **All tests passed:** /
- **Critical bugs found:** [List here]
- **Minor issues found:** [List here]

### Recommendation

- [ ] **SAFE TO MERGE** - All tests passed
- [ ] **NEEDS FIXES** - Minor issues, but functional
- [ ] **DO NOT MERGE** - Critical bugs found

---

## Notes & Observations

```
[Add additional observations, screenshots, or comments here]
```

---

## Appendix: Test Data

### Used Orders

| Invoice | Items | Status | Marked as |
|---------|-------|--------|-----------|
| INV-_____ | Physical | PAID_AWAITING_SHIPMENT | Shipped / Cancelled |
| INV-_____ | Mixed | PAID_AWAITING_SHIPMENT | - |
| INV-_____ | Physical | PAID_AWAITING_SHIPMENT | - |

---

**Test completed on:** [Date/Time]
**Tester signature:** [Name]
