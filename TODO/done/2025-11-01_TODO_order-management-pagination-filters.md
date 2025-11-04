# Order Management with Pagination and Status Filters

**Priority:** High
**Status:** TODO
**Estimated Effort:** Large (8-12 hours)
**Related TODOs:**
- 2025-11-01_TODO_invoice-formatter-refactoring.md (should be done first)

## Description

Refactor Admin Shipping Management into comprehensive Order Management System with:
- Pagination for large order lists
- Status filters for all OrderStatus values
- Display all orders within data retention time (not just PAID_AWAITING_SHIPMENT)
- Consistent display format: Date - Time - Order-ID (Invoice-ID) - STATUS
- Enhanced order detail view with payment history and admin actions based on order state
- Highlight orders requiring action (especially PAID_AWAITING_SHIPMENT)

## Current State

Currently `handlers/admin/shipping_management.py`:
- Only shows orders with status `PAID_AWAITING_SHIPMENT`
- No pagination (all orders at once)
- No filtering capability
- Focused on shipping workflow only
- Limited order details view

## Requirements

### 1. Order List Overview (Level 0)
- All orders within Data Retention Time (30 days default)
- Format: `Date - Time - Order-ID - STATUS`
  - Date: `DD.MM.YYYY`
  - Time: `HH:MM`
  - Order-ID: Invoice Number (e.g. `INV-2025-000123`)
  - Status: Localized from language files (l10n/de.json, l10n/en.json)
- Visual indicator for orders requiring action (e.g.    for PAID_AWAITING_SHIPMENT)
- Each order is clickable → navigates to order detail view (Level 1)

### 2. Status Filters (Level -1)

**All OrderStatus values filterable:**
- `PENDING_PAYMENT`
- `PENDING_PAYMENT_AND_ADDRESS`
- `PENDING_PAYMENT_PARTIAL`
- `PAID` (digital only)
- `PAID_AWAITING_SHIPMENT`   **REQUIRES SHIPPING ACTION**
- `SHIPPED`
- `CANCELLED_BY_USER`
- `CANCELLED_BY_ADMIN`
- `CANCELLED_BY_SYSTEM`
- `TIMEOUT`

**Filter groups:**
- **Requires Action** (PAID_AWAITING_SHIPMENT) - Default filter!  
- All orders
- Active (PENDING_*, PAID*, PAID_AWAITING_SHIPMENT)
- Completed (PAID, SHIPPED)
- Cancelled (CANCELLED_*, TIMEOUT)
- Individual status filters

### 3. Order Detail View (Level 1)

**Display same invoice view as user sees:**
- Use same invoice formatting logic
- Show all order items (digital + physical)
- Show pricing breakdown
- Show shipping address (if physical items)

**Additional admin information:**

**Payment History Section:**
- Order creation timestamp: `DD.MM.YYYY HH:MM:SS`
- Payment received timestamp: `DD.MM.YYYY HH:MM:SS` (if paid)
- Payment method: Wallet, Crypto (with currency), or Mixed
- Payment details:
  - Wallet amount used (if any)
  - Crypto payment details:
    - Currency (BTC, ETH, LTC, SOL, BNB)
    - Amount paid
    - KryptoExpress transaction ID
    - KryptoExpress order ID
    - Payment address used
    - Confirmation timestamp
  - Underpayment retries (if any)
  - Late payment penalty (if applied)

**Admin Actions (based on order state):**

Rules:
- `PAID_AWAITING_SHIPMENT`: **Mark as Shipped** button (primary action)  
- `SHIPPED`: No actions available (order complete)
- Physical items + NOT `SHIPPED`: Cancel button available
- Digital items + `PAID`: No cancel action (items already delivered)
- Any other status: Cancel button available

Actions:
- [ ] **Mark as Shipped** (only for `PAID_AWAITING_SHIPMENT`) - PRIMARY
- [ ] Cancel Order (with reason input via FSM)
- [ ] View User Profile
- [ ] View Payment Details (expandable section)

### 4. Pagination
- 10 orders per page (configurable)
- Navigation: "◀️ Back" | "Page X/Y" | "Next ▶️"
- Pagination state in callback data
- Filter + page state preserved across navigation

## Implementation Plan

### Phase 1: Repository Layer
- [ ] Add `OrderRepository.get_orders_in_retention_period()`:
  - Parameters:
    - `status_filter: Optional[List[OrderStatus]]` - Filter by status (None = all)
    - `limit: int = 10` - Items per page
    - `offset: int = 0` - Pagination offset
    - `session: AsyncSession | Session`
  - JOIN Invoice for invoice_number
  - JOIN User for user info
  - Filter by `order.created_at >= (now() - retention_days)`
  - Order by `created_at DESC`

- [ ] Add `OrderRepository.count_orders_in_retention_period()`:
  - Same filters as above
  - Return total count

- [ ] Add `OrderRepository.get_order_payment_history()`:
  - Fetch order with all payment-related data
  - Include Invoice, PaymentTransaction records
  - Include underpayment history
  - Include penalty information

### Phase 2: Payment History Service
- [ ] Add `PaymentService.get_payment_history_details()`:
  - Parameters: `order_id: int`, `session: AsyncSession | Session`
  - Return structured payment history:
    ```python
    {
        "order_created_at": datetime,
        "payment_received_at": Optional[datetime],
        "wallet_amount_used": Decimal,
        "crypto_payments": [
            {
                "currency": str,
                "amount": Decimal,
                "kryptoexpress_transaction_id": str,
                "kryptoexpress_order_id": str,
                "payment_address": str,
                "confirmed_at": datetime
            }
        ],
        "underpayment_retries": int,
        "late_payment_penalty": Decimal,
        "total_paid": Decimal
    }
    ```

### Phase 3: Localization
- [ ] Add status translations (if missing):
  - Use existing keys or add: `order_status_*` for each OrderStatus
  - Special emphasis on `order_status_paid_awaiting_shipment` (highlight action needed)

- [ ] Add new admin strings:
  - `admin_order_management_title` ("Order Management")
  - `admin_order_filter_label` ("Filter: {filter_name}")
  - `admin_order_pagination_info` ("Page {current}/{total}")
  - `admin_order_no_orders` ("No orders found")
  - `admin_order_requires_action` ("  Requires Shipping")
  - `admin_order_payment_history_title` ("Payment History")
  - `admin_order_created_at` ("Order created")
  - `admin_order_paid_at` ("Payment received")
  - `admin_order_payment_method` ("Payment method")
  - `admin_order_wallet_used` ("Wallet amount")
  - `admin_order_crypto_payment` ("Crypto payment")
  - `admin_order_kryptoexpress_tx_id` ("KryptoExpress TX ID")
  - `admin_order_kryptoexpress_order_id` ("KryptoExpress Order ID")
  - `admin_order_payment_address` ("Payment address")
  - `admin_order_underpayment_retries` ("Underpayment retries")
  - `admin_order_late_penalty` ("Late payment penalty")
  - `admin_order_action_mark_shipped` ("  Mark as Shipped")
  - `admin_order_action_cancel` ("Cancel Order")
  - `admin_order_action_view_user` ("View User Profile")
  - `admin_order_no_actions` ("No actions available")

- [ ] Add filter group labels:
  - `admin_order_filter_requires_action` ("  Requires Action")
  - `admin_order_filter_all`
  - `admin_order_filter_active`
  - `admin_order_filter_completed`
  - `admin_order_filter_cancelled`

### Phase 4: Callback Updates
- [ ] Extend or create `OrderManagementCallback`:
  - `level: int` (navigation level)
  - `order_id: Optional[int]` (for detail view)
  - `page: int = 0` (pagination)
  - `status_filter: Optional[str] = None` (serialized filter)

- [ ] Maintain backwards compatibility with `ShippingManagementCallback`
  - Map old callbacks to new system
  - **Default filter: `PAID_AWAITING_SHIPMENT` (same as before)**

### Phase 5: Handler Implementation

**Level -1: Filter Selection**
- [ ] Implement `show_order_filters()`:
  - **"  Requires Action" at the top (PAID_AWAITING_SHIPMENT)**
  - Display filter groups as buttons
  - Each button navigates back to Level 0 with filter applied
  - Current filter highlighted

**Level 0: Order List**
- [ ] Refactor `show_awaiting_shipment_orders()` → `show_orders_list()`:
  - **Default filter: PAID_AWAITING_SHIPMENT (maintains current behavior)**
  - Read pagination state from callback_data
  - Read filter from callback_data
  - Fetch orders via `OrderRepository.get_orders_in_retention_period()`
  - Build order list buttons with visual indicators:
    -    for PAID_AWAITING_SHIPMENT (requires action)
    -    for SHIPPED
    -    for cancelled/timeout
    -   for others
  - Add pagination buttons (if needed)
  - Add filter button at top (shows current filter)
  - Add back to main menu button

**Level 1: Order Details**
- [ ] Refactor `show_order_details()`:
  - Fetch order with all details
  - Display invoice (reuse existing invoice formatter or implement new one)
  - Add Payment History section:
    - Call `PaymentService.get_payment_history_details()`
    - Format payment history as readable text
    - Include all KryptoExpress details
  - Determine available admin actions:
    - **Check if PAID_AWAITING_SHIPMENT → show "Mark as Shipped" prominently**
    - Check if cancellation allowed (rules above)
  - Build action buttons dynamically
  - Add back button (preserve pagination + filter state)

**Level 2+: Existing Shipping Actions**
- [ ] Keep existing shipping workflow
- [ ] Ensure compatibility with new navigation

### Phase 6: Admin Action Logic

**Mark as Shipped Action:**
- [ ] Only available for `PAID_AWAITING_SHIPMENT`
- [ ] Call `ShippingService.mark_order_shipped()`
- [ ] Send notification to user
- [ ] Return to order list (with filter + page preserved)

**Cancel Order Action:**
- [ ] Reuse existing cancellation FSM from `admin_order_cancellation.py`
- [ ] Validate cancellation rules:
  - SHIPPED: Not allowed
  - Digital + PAID: Not allowed
  - All others: Allowed
- [ ] Show error if not allowed

### Phase 7: Keyboard Building
- [ ] Pagination logic:
  - Calculate: `total_pages = ceil(total_count / page_size)`
  - Show "◀️ Prev" if `page > 0`
  - Show "Page X/Y" (info button)
  - Show "Next ▶️" if `page < total_pages - 1`

- [ ] Filter button:
  - Display current filter name with icon
  - **"  Requires Action" for PAID_AWAITING_SHIPMENT filter**
  - Navigate to Level -1

- [ ] Order buttons:
  - One row per order
  - Format: `{icon} {date} - {time} - {invoice_id} - {status}`
  - Icons based on status (visual indicators)
  - Navigate to Level 1 with order_id

- [ ] Action buttons (Level 1):
  - Dynamic based on order state
  - **"  Mark as Shipped" as primary action (top) for PAID_AWAITING_SHIPMENT**
  - Always: "Back to Order List"

### Phase 8: Testing
- [ ] Empty state (no orders)
- [ ] Single page (1-10 orders)
- [ ] Multiple pages (50+ orders)
- [ ] All status filters
- [ ] **Default filter (PAID_AWAITING_SHIPMENT) works correctly**
- [ ] Filter + pagination combination
- [ ] Order detail view for each status
- [ ] **PAID_AWAITING_SHIPMENT detail view with "Mark as Shipped" button**
- [ ] Payment history display:
  - Wallet-only payment
  - Crypto-only payment
  - Mixed payment
  - Underpayment retry
  - Late payment penalty
- [ ] Admin actions:
  - **Mark as shipped (PAID_AWAITING_SHIPMENT)**
  - Cancel allowed (various statuses)
  - Cancel not allowed (SHIPPED, digital+PAID)
- [ ] Navigation state preservation
- [ ] Performance with 1000+ orders

### Phase 9: Configuration
- [ ] Add to config.py:
  - `ADMIN_ORDERS_PER_PAGE` (default: 10)
  - Reuse: `DATA_RETENTION_SHIPPING_DAYS` (default: 30)

- [ ] Document in .env.template

## Technical Notes

### Default Filter Behavior
- **System starts with filter = PAID_AWAITING_SHIPMENT (backwards compatible)**
- This ensures admins immediately see orders requiring shipping action
- Admins can change filter to see other orders

### Visual Indicators by Status
```python
STATUS_ICONS = {
    OrderStatus.PAID_AWAITING_SHIPMENT: "  ",  # Requires action!
    OrderStatus.SHIPPED: "  ",
    OrderStatus.PAID: " ",
    OrderStatus.CANCELLED_BY_USER: "  ",
    OrderStatus.CANCELLED_BY_ADMIN: "  ",
    OrderStatus.CANCELLED_BY_SYSTEM: "  ",
    OrderStatus.TIMEOUT: "  ",
    # ... others: " "
}
```

### Payment History Data Sources
- `Order.created_at` → Order creation timestamp
- `Invoice.paid_at` → Payment received timestamp
- `Invoice.wallet_amount` → Wallet usage
- `PaymentTransaction` table → Crypto payment details
  - Fields: currency, amount, kryptoexpress_tx_id, payment_address, confirmed_at
- `Order.underpayment_retry_count` → Retry tracking
- `Order.late_payment_penalty` → Penalty amount

### Admin Action Rules (Logic)
```python
def get_available_actions(order: Order) -> List[str]:
    actions = []

    # PRIMARY: Mark as shipped (for PAID_AWAITING_SHIPMENT)
    if order.status == OrderStatus.PAID_AWAITING_SHIPMENT:
        actions.append("mark_shipped")

    # Cancel action
    if can_cancel_order(order):
        actions.append("cancel")

    # Always available
    actions.append("view_user")

    return actions

def can_cancel_order(order: Order) -> bool:
    # Cannot cancel if shipped
    if order.status == OrderStatus.SHIPPED:
        return False

    # Cannot cancel digital items that are already paid (delivered)
    if order.status == OrderStatus.PAID:
        has_only_digital = all(not item.is_physical for item in order.order_items)
        if has_only_digital:
            return False

    return True
```

### Display Format Examples

**Order List (Default: Requires Action):**
```
  Order Management
  Filter: Versand erforderlich

   01.11.2025 - 14:35 - INV-2025-000123 - Bezahlt (Versand ausstehend)
   01.11.2025 - 12:20 - INV-2025-000122 - Bezahlt (Versand ausstehend)
   31.10.2025 - 18:45 - INV-2025-000121 - Bezahlt (Versand ausstehend)

[◀️ Zurück] [Seite 1/3] [Weiter ▶️]
[  Filter ändern]
[🏠 Hauptmenü]
```

**Order Detail with Payment History (PAID_AWAITING_SHIPMENT):**
```
  Rechnung INV-2025-000123
  VERSAND ERFORDERLICH

[... existing invoice format ...]

💳 Zahlungshistorie

Bestellung erstellt: 01.11.2025 14:35:22
Zahlung erhalten: 01.11.2025 14:42:18

Zahlungsmethode: Gemischt (Wallet + BTC)

Wallet verwendet: 15.50 EUR
Krypto-Zahlung (BTC): 0.00123 BTC (≈ 84.50 EUR)

  KryptoExpress Details:
TX-ID: kxp_tx_abc123def456
Order-ID: kxp_order_789xyz
Zahlungsadresse: bc1qxy2kgdygjrsqtzq2n0yrf...
Bestätigt: 01.11.2025 14:42:18

Verspätungszuschlag: 0.00 EUR
Unterzahlungsversuche: 0

Gesamt bezahlt: 100.00 EUR

───────────────────────
Admin-Aktionen:

[  Als versendet markieren]  ← PRIMARY ACTION
[Bestellung stornieren]
[Benutzerprofil anzeigen]

[⬅️ Zurück zur Liste]
```

## Benefits

-   **Maintains current "awaiting shipment" workflow (default filter)**
-   Complete order overview for admins
-   Efficient navigation with pagination
-   Flexible status filtering
-   Full payment transparency (KryptoExpress integration)
-   Context-aware admin actions
-   Better support for customer inquiries
-   Audit trail for payments
-   Performance-optimized

## Migration Notes

- **Default behavior unchanged: Shows PAID_AWAITING_SHIPMENT orders first**
- Rename or extend existing `ShippingManagementCallback` to `OrderManagementCallback`
- Keep existing shipping workflow (Level 1-4 actions)
- Add new Level -1 (filters) and enhanced Level 0 (list) and Level 1 (details)
- Backwards compatibility for old callback links

## Dependencies

- Depends on: Data Retention Cleanup Job (implemented)
- Depends on: PaymentTransaction table structure
- Nice-to-have: Invoice Formatter Refactoring (integrate after)

## Related TODOs

- `2025-11-01_TODO_invoice-formatter-refactoring.md` - Use for consistent invoice display

## Estimated Timeline

- Phase 1 (Repository): 1-2h
- Phase 2 (Payment History Service): 1-2h
- Phase 3 (Localization): 1h
- Phase 4 (Callbacks): 30min
- Phase 5 (Handlers): 3-4h
- Phase 6 (Admin Actions): 1h
- Phase 7 (Keyboard): 1h
- Phase 8 (Testing): 2-3h
- Phase 9 (Config): 15min

**Total: 10-14 hours**