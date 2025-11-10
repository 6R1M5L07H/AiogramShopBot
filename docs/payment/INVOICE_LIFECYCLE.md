# Invoice Lifecycle Documentation

## Overview

This document describes the complete lifecycle of invoices in the AiogramShopBot payment system, including state transitions, triggers, and implementation details.

## Invoice States

Invoices use a soft-delete pattern with the `is_active` flag:
- `is_active = 1`: Active invoice (valid payment address)
- `is_active = 0`: Inactive invoice (expired, cancelled, or superseded)

Inactive invoices are preserved for audit trail and compliance purposes.

## State Transitions

### 1. Invoice Creation

**Trigger:** User selects cryptocurrency for order payment

**Preconditions:**
- Order exists with status `PENDING_PAYMENT` or `PENDING_PAYMENT_AND_ADDRESS`
- No active invoice exists for order
- Wallet balance insufficient to cover full order amount

**Process:**
1. Call `InvoiceService.create_invoice_with_kryptoexpress()`
2. Request payment address from KryptoExpress API
3. Generate unique invoice number (format: `INV-YYYY-XXXXXX`)
4. Create invoice record with `is_active = 1`
5. Set `order.expires_at = now() + 30 minutes`

**Result:**
- Invoice created with active payment address
- Order status: `PENDING_PAYMENT`
- User sees: Payment address, QR code, countdown timer

**Code:** `services/invoice.py:create_invoice_with_kryptoexpress()`

---

### 2. Wallet-Only Payment

**Trigger:** Wallet balance covers full order amount

**Preconditions:**
- User wallet balance >= order total price
- User navigates to payment step

**Process:**
1. Deduct full amount from user wallet
2. Create tracking invoice (no payment address)
3. Mark order as PAID immediately
4. Deliver items (mark as sold, create buy records)

**Invoice Fields:**
```python
payment_address = None
payment_amount_crypto = None
payment_crypto_currency = None
payment_processing_id = None
fiat_amount = order.total_price
is_active = 1  # Active for audit trail
```

**Result:**
- Order status: `PAID`
- No crypto payment required
- Invoice serves as payment record

**Code:** `services/payment.py:orchestrate_payment_processing()` (lines 179-198)

---

### 3. Mixed Payment (Wallet + Crypto)

**Trigger:** Wallet balance partially covers order amount

**Preconditions:**
- 0 < wallet balance < order total price
- User navigates to payment step

**Process:**
1. Deduct available wallet balance
2. Calculate remaining amount
3. Create invoice for remaining amount only
4. Request payment address from KryptoExpress

**Invoice Fields:**
```python
fiat_amount = order.total_price - wallet_used  # REST amount only!
payment_address = <crypto_address>
is_active = 1
```

**Result:**
- Order status: `PENDING_PAYMENT`
- `order.wallet_used` set to deducted amount
- User pays remaining amount via crypto

**Code:** `services/payment.py:orchestrate_payment_processing()` (lines 156-178)

---

### 4. Successful Payment

**Trigger:** KryptoExpress webhook with status PAID

**Preconditions:**
- Invoice exists with `is_active = 1`
- Payment received matches expected amount (within tolerance)

**Process:**
1. Create `PaymentTransaction` record
2. Update order status to `PAID`
3. Mark items as sold
4. Create buy records
5. Deliver digital items immediately
6. Notify user of successful payment

**Invoice State:**
- `is_active = 1` (remains active as payment record)

**Result:**
- Order status: `PAID` or `PAID_AWAITING_SHIPMENT`
- Items delivered (digital) or awaiting shipment (physical)

**Code:** `processing/payment_handlers.py:handle_paid_status()`

---

### 5. Order Timeout

**Trigger:** Background job runs after `order.expires_at`

**Preconditions:**
- Order status: `PENDING_PAYMENT*`
- Current time > `order.expires_at`
- No payment received

**Process:**
1. Update order status to `TIMEOUT`
2. Mark all invoices as inactive: `is_active = 0`
3. Release reserved items (restore stock)
4. Add strike to user (if outside grace period)
5. Notify user of timeout

**Invoice State:**
- `is_active = 0` (expired)

**Result:**
- Order status: `TIMEOUT`
- Items returned to stock
- User may receive strike

**Code:** `jobs/order_timeout_job.py`

---

### 6. User Cancellation

**Trigger:** User clicks "Cancel Order" button

**Preconditions:**
- Order status: `PENDING_PAYMENT*`
- Order not yet paid

**Process:**
1. Update order status to `CANCELLED_BY_USER`
2. Mark all invoices as inactive: `is_active = 0`
3. Refund wallet if used (may include penalty)
4. Release reserved items
5. Add strike if outside grace period (5 minutes default)

**Invoice State:**
- `is_active = 0` (cancelled)

**Result:**
- Order status: `CANCELLED_BY_USER`
- Wallet refunded (minus penalty if late)
- Possible strike for user

**Code:** `services/order.py:cancel_order()` (line 772)

---

### 7. Admin Cancellation

**Trigger:** Admin clicks "Cancel Order" (with or without reason)

**Preconditions:**
- Order status: `PENDING_PAYMENT*` or `PAID_AWAITING_SHIPMENT`
- Admin has cancellation permission

**Process:**
1. Update order status to `CANCELLED_BY_ADMIN`
2. Mark all invoices as inactive: `is_active = 0`
3. Full wallet refund (no penalty)
4. Release reserved items
5. Notify user with custom reason (if provided)

**Invoice State:**
- `is_active = 0` (cancelled by admin)

**Result:**
- Order status: `CANCELLED_BY_ADMIN`
- Full refund to user
- No strike applied

**Code:** `handlers/admin/shipping_management.py:cancel_order_admin_execute()`

---

### 8. Underpayment

**Trigger:** KryptoExpress webhook with UNDERPAYMENT status

**Preconditions:**
- Payment received < expected amount (outside tolerance)
- Invoice exists with `is_active = 1`

**Process:**
1. Create `PaymentTransaction` record (for audit)
2. Update order status to `CANCELLED_BY_SYSTEM`
3. Mark invoice as inactive: `is_active = 0`
4. Release reserved items
5. Credit received amount to user wallet
6. Notify user of cancellation and wallet credit

**Invoice State:**
- `is_active = 0` (cancelled due to underpayment)

**Result:**
- Order status: `CANCELLED_BY_SYSTEM`
- User wallet credited with received amount
- User must create new order

**Code:** `processing/payment_handlers.py:handle_underpayment()`

**Note:** No automatic retry. User must create new order with full payment.

---

### 9. Late Payment

**Trigger:** KryptoExpress webhook AFTER `order.expires_at` BUT BEFORE timeout job

**Preconditions:**
- Payment received after expiration timestamp
- Order not yet cancelled by timeout job (race condition window)
- Payment amount correct

**Process:**
1. Create `PaymentTransaction` record (no penalty flag)
2. Update order status to `PAID`
3. Mark items as sold
4. Deliver items immediately
5. Notify user of successful payment

**Invoice State:**
- `is_active = 1` (remains active, payment accepted)

**Result:**
- Order status: `PAID` or `PAID_AWAITING_SHIPMENT`
- **NO penalty applied** (purchase completed = no opportunity cost)
- Items delivered normally

**Important:** Penalty is ONLY applied when purchase is aborted (timeout/cancellation), NOT when items are delivered. Late payment that arrives before timeout job runs is treated as normal successful payment.

**Code:** `processing/payment_handlers.py` (checks `expires_at` timestamp)

---

## Invoice Query Patterns

### Active Invoices Only (Default)

Used for payment processing and user-facing displays:

```python
invoice = await InvoiceRepository.get_by_order_id(
    order_id,
    session,
    include_inactive=False  # Default
)
```

### All Invoices (Audit Trail)

Used for payment history, admin views, and debugging:

```python
invoices = await InvoiceRepository.get_all_by_order_id(
    order_id,
    session,
    include_inactive=True  # Include expired/cancelled
)
```

---

## State Diagram

```
                    [ORDER CREATED]
                          |
                          v
                  Choose Payment Method
                    /            \
                   /              \
            [Wallet >= Total]  [Wallet < Total]
                  |                  |
                  v                  v
          Wallet-Only Invoice   Mixed/Crypto Invoice
          (no payment address)  (KryptoExpress address)
                  |                  |
                  |                  v
                  |           User pays crypto
                  |                  |
                  +------------------+
                          |
                          v
                    Payment Received
                    /      |      \
                   /       |       \
            [On Time] [Late] [Underpaid]
                |       |          |
                v       v          v
              PAID    PAID    CANCELLED_BY_SYSTEM
          (is_active=1) (no penalty) (is_active=0, refund to wallet)
```

**Cancellation paths (from any PENDING state):**
- User Cancel -> CANCELLED_BY_USER (is_active=0)
- Admin Cancel -> CANCELLED_BY_ADMIN (is_active=0)
- Timeout -> TIMEOUT (is_active=0)

**Expired order access:**
- User navigates to expired order -> Redirect to cart with error message
- No invoice renewal possible - user must create new order

---

## Database Schema

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    invoice_number VARCHAR UNIQUE NOT NULL,
    payment_address VARCHAR,
    payment_amount_crypto FLOAT,
    payment_crypto_currency VARCHAR,
    payment_processing_id INTEGER,
    fiat_amount FLOAT NOT NULL,
    fiat_currency VARCHAR NOT NULL,
    is_partial_payment INTEGER DEFAULT 0,
    parent_invoice_id INTEGER,
    actual_paid_amount_crypto FLOAT,
    payment_attempt INTEGER DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,  -- Soft delete flag
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (parent_invoice_id) REFERENCES invoices(id)
);

CREATE INDEX idx_invoices_is_active ON invoices(is_active);
```

---

## Related Tables

### PaymentTransaction

Created when payment is received (success, underpayment, or late payment):

```python
class PaymentTransaction:
    invoice_id: int
    payment_processing_id: int  # KryptoExpress transaction ID
    crypto_amount: float
    crypto_currency: Cryptocurrency
    fiat_amount: float
    transaction_hash: str
    received_at: datetime
    is_underpayment: bool
    is_overpayment: bool
    is_late_payment: bool
    penalty_applied: bool
    penalty_percent: float
```

### Order Status Values

```python
class OrderStatus(Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PENDING_PAYMENT_AND_ADDRESS = "PENDING_PAYMENT_AND_ADDRESS"
    PENDING_PAYMENT_PARTIAL = "PENDING_PAYMENT_PARTIAL"
    PAID = "PAID"
    PAID_AWAITING_SHIPMENT = "PAID_AWAITING_SHIPMENT"
    SHIPPED = "SHIPPED"
    TIMEOUT = "TIMEOUT"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    CANCELLED_BY_ADMIN = "CANCELLED_BY_ADMIN"
    CANCELLED_BY_SYSTEM = "CANCELLED_BY_SYSTEM"
```

---

## Configuration

Relevant configuration variables:

```python
ORDER_TIMEOUT_MINUTES = 30  # Payment window duration
ORDER_CANCEL_GRACE_PERIOD_MINUTES = 5  # Free cancellation period
PAYMENT_LATE_PENALTY_PERCENT = 5.0  # Late payment penalty
PAYMENT_UNDERPAYMENT_TOLERANCE_PERCENT = 2.0  # Acceptable underpayment
```

---

## Migration History

- `009_add_invoice_is_active.sql`: Added `is_active` column for soft delete
  - Marks invoices for cancelled orders as inactive
  - Creates index on `is_active` for query performance
