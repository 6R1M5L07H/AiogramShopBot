# Exception Handling - Manual Test Scenarios

This document provides concrete test cases to verify the exception handling improvements (Phase 1 + Phase 2).

## Prerequisites

- Bot running locally or on test server
- Admin account configured
- At least one test user account
- Some test orders in database

## Test Group 1: Order Exceptions (User Side)

### Test 1.1: OrderNotFoundException in Purchase History

**Steps:**
1. Open bot as user
2. Navigate to "My Profile" → "Purchase History"
3. Manually tamper with callback data to reference non-existent order_id (e.g., 999999)
   - Or: Delete an order from DB, then try to view it from history

**Expected Result:**
- Alert popup: "  Order not found"
- No crash, graceful error handling
- User can navigate back

**Localization Check:**
- English: "  Order not found"
- German: "  Bestellung nicht gefunden"

---

## Test Group 2: Order Exceptions (Admin Side)

### Test 2.1: OrderNotFoundException in Shipping Management

**Steps:**
1. Open bot as admin
2. Navigate to Admin Menu → Shipping Management
3. Click on an order
4. Delete the order from database manually (or use invalid order_id in callback)
5. Try to mark as shipped or cancel

**Expected Result:**
- Message: "  Order not found"
- Back button shows
- No crash

### Test 2.2: InvalidOrderStateException - Cancel Already Cancelled Order

**Steps:**
1. Open bot as admin
2. Navigate to Shipping Management
3. Cancel an order successfully
4. Try to cancel the same order again (need to manually trigger callback)

**Expected Result:**
- Message: "  Cannot cancel order: Order is {current_state}"
- Shows current order state
- Back button available

### Test 2.3: InvalidOrderStateException - Ship Already Shipped Order

**Steps:**
1. Mark an order as shipped
2. Try to mark same order as shipped again (need to manually trigger callback)

**Expected Result:**
- Error message showing order is already shipped
- No crash

---

## Test Group 3: Item Exceptions

### Test 3.1: ItemNotFoundException in Category Browse

**Setup:**
1. Create category with items
2. Delete item from DB while user is browsing

**Steps:**
1. User browses category
2. Click on item that was just deleted

**Expected Result:**
- Alert: "  Item not available"
- User returns to category view
- No crash

**Localization Check:**
- English: "  Item not available."
- German: "  Artikel nicht verfügbar."

### Test 3.2: InsufficientStockException

**Steps:**
1. Find item with limited stock (e.g., 2 available)
2. Add 10 items to cart

**Expected Result:**
- Error message: "  Insufficient stock: 2 available, 10 requested."
- Cart operation blocked
- Clear error message

**Localization Check:**
- English: "  Insufficient stock: {available} available, {requested} requested."
- German: "  Unzureichender Bestand: {available} verfügbar, {requested} angefordert."

---

## Test Group 4: Payment Exceptions

### Test 4.1: CryptocurrencyNotSelectedException

**Steps:**
1. Navigate to "Top Up Balance"
2. Skip cryptocurrency selection (manipulate callback if needed)
3. Try to create payment without selecting crypto

**Expected Result:**
- Alert: "  Please select a cryptocurrency first."
- Redirected to cryptocurrency selection

**Localization Check:**
- English: "  Please select a cryptocurrency first."
- German: "  Bitte wähle zuerst eine Kryptowährung."

### Test 4.2: InsufficientBalanceException

**Steps:**
1. User with €5 balance
2. Try to purchase item worth €10
3. Attempt wallet payment

**Expected Result:**
- Error: "  Insufficient balance: €10.00 required, €5.00 available."
- Purchase blocked
- Clear feedback

**Localization Check:**
- English: "  Insufficient balance: €{required:.2f} required, €{available:.2f} available."
- German: "  Unzureichendes Guthaben: €{required:.2f} benötigt, €{available:.2f} verfügbar."

---

## Test Group 5: User Exceptions

### Test 5.1: UserBannedException

**Steps:**
1. Ban a test user with reason "Test ban - violation"
2. Banned user tries to interact with bot

**Expected Result:**
- Error: "  You are banned: Test ban - violation"
- User cannot proceed with actions
- Reason is displayed

**Localization Check:**
- English: "  You are banned: {reason}"
- German: "  Du bist gebannt: {reason}"

---

## Test Group 6: Generic Exception Handling

### Test 6.1: Unexpected Exception

**Steps:**
1. Simulate unexpected error (e.g., database connection loss during operation)
2. Trigger any protected handler function

**Expected Result:**
- User message: "  An unexpected error occurred. Please try again later."
- Error logged to server logs with full traceback
- No crash, user can continue

**Localization Check:**
- English: "  An unexpected error occurred. Please try again later."
- German: "  Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später erneut."

---

## Test Group 7: FSM State Cleanup

### Test 7.1: State Cleanup on Error in Admin Order Cancellation

**Steps:**
1. Admin starts order cancellation flow
2. Enters "waiting_for_cancellation_reason" state
3. Trigger error (e.g., order gets deleted)
4. Verify FSM state is cleared

**Expected Result:**
- FSM state properly cleared
- No stuck state
- User can start new operation

---

## Test Group 8: Item Grouping (Bonus - from previous work)

### Test 8.1: Identical Physical Items Grouped

**Steps:**
1. Add 5 identical physical items to cart (same name, price, no private_data)
2. Checkout with wallet payment

**Expected Result:**
- Order confirmation shows: "5 Stk. Item Name €10.00 = €50.00"
- Not 5 separate lines

### Test 8.2: Items with Unique Private Data NOT Grouped

**Steps:**
1. Purchase 3 digital items (e.g., game keys) in single order
2. Each has unique private_data

**Expected Result:**
- 3 separate line items shown
- Each with its unique private_data displayed
- NOT grouped

### Test 8.3: Mixed Items Grouped Correctly

**Steps:**
1. Cart with:
   - 3x Physical Item A (identical)
   - 2x Digital Item B with private_data=None (identical)
   - 1x Digital Item C with private_data="KEY123" (unique)
   - 1x Digital Item C with private_data="KEY456" (unique)

**Expected Result:**
- Line 1: "3 Stk. Physical Item A"
- Line 2: "2 Stk. Digital Item B"
- Line 3: "1 Stk. Digital Item C" (KEY123)
- Line 4: "1 Stk. Digital Item C" (KEY456)

---

## Automated Testing Helper

For some scenarios, you can use Python scripts to simulate conditions:

```python
# Example: Simulate OrderNotFoundException
from sqlalchemy import select
from models.order import Order

# In test script:
order_id = 999999  # Non-existent
# Then trigger callback with this order_id
```

---

## Quick Smoke Test Checklist

Minimal test coverage to verify basic functionality:

- [ ] Test 1.1: User views non-existent order → Error shown
- [ ] Test 2.1: Admin cancels non-existent order → Error shown
- [ ] Test 3.1: User clicks deleted item → Error shown
- [ ] Test 4.2: User purchases with insufficient balance → Error shown
- [ ] Test 5.1: Banned user tries action → Error shown
- [ ] Test 8.1: Identical items grouped in order confirmation

---

## Notes

- Most tests require database manipulation or callback tampering
- Use test environment, NOT production
- Check both English and German localizations
- Verify logging for unexpected errors
- Ensure no bot crashes occur during any test
