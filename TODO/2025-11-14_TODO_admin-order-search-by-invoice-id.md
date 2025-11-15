# TODO: Admin Order Search by Invoice ID

**Created:** 2025-11-14
**Priority:** Medium
**Status:** Planning

## Problem Statement

Admin needs ability to search for orders by Invoice ID during customer support interactions. Currently, admins must scroll through paginated order lists to find specific orders, which is inefficient when customer provides their invoice number.

## User Story

**As an** admin handling customer support
**I want to** search orders by Invoice ID (e.g., "INV-2025-ABC123")
**So that** I can quickly locate and view order details when customer contacts me

## Requirements

### Functional Requirements

1. **Search Input**
   - Free-text input field for Invoice ID search
   - **Format validation: `INV-YYYY-XXXXXX` (3 chars + 4 digits + 6 alphanumeric)**
   - Accept full invoice numbers only (no partial search for security)
   - Case-insensitive search (normalize to uppercase)
   - Trim whitespace from input
   - Reject malformed inputs immediately

2. **Search Results**
   - If found: Display order detail view directly
   - If not found: Show error message with "Try Again" and "Back to Orders" buttons
   - If format invalid: Show format hint and "Try Again" button

3. **Navigation**
   - Add "Search by Invoice ID" button to Shipping Management menu (Level 0)
   - Use FSM state to capture text input
   - Maintain filter/page context for back navigation

### Technical Requirements

1. **FSM State**
   - New state: `AdminOrderSearchStates.waiting_for_invoice_id`
   - Store current filter/page in FSM for back navigation

2. **Input Validation**
   - Regex pattern: `^INV-\d{4}-[A-Z0-9]{6}$`
   - Validate BEFORE database query
   - Reject any input not matching pattern

3. **Repository Method**
   - `OrderRepository.get_by_invoice_number(invoice_number, session)`
   - Query invoices table with exact match (no LIKE - security)
   - Return single order ID or None

4. **Service Method**
   - `OrderManagementService.search_order_by_invoice()`
   - Handle validation and search logic
   - Build result UI

5. **Handler Integration**
   - New callback level: `ShippingManagementCallback.level=11` (Search by Invoice ID)
   - Text handler for FSM state input with validation
   - Reuse existing `OrderManagementService.get_order_detail_view()`

## Implementation Plan

### Phase 1: Validation Utility

**File:** `utils/invoice_validator.py` (NEW)

```python
import re
from typing import Optional


class InvoiceValidator:
    """
    Validates invoice number format and extracts components.

    Format: INV-YYYY-XXXXXX
    - INV: Fixed prefix
    - YYYY: 4-digit year (e.g., 2025)
    - XXXXXX: 6 alphanumeric characters (uppercase)
    """

    INVOICE_PATTERN = re.compile(r'^INV-(\d{4})-([A-Z0-9]{6})$', re.IGNORECASE)

    @staticmethod
    def validate(invoice_input: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate invoice number format.

        Args:
            invoice_input: Raw input string from user

        Returns:
            Tuple of (is_valid, normalized_invoice, error_message)
            - is_valid: True if format matches
            - normalized_invoice: Uppercase normalized format (e.g., "INV-2025-ABC123")
            - error_message: Human-readable error if invalid
        """
        # Normalize input
        invoice_input = invoice_input.strip().upper()

        # Empty check
        if not invoice_input:
            return False, None, "Invoice number cannot be empty."

        # Length check (security: prevent excessively long inputs)
        if len(invoice_input) > 50:
            return False, None, "Invoice number too long."

        # Format check
        match = InvoiceValidator.INVOICE_PATTERN.match(invoice_input)
        if not match:
            return False, None, (
                "Invalid invoice format.\n"
                "Expected format: <code>INV-YYYY-XXXXXX</code>\n"
                "Example: <code>INV-2025-ABC123</code>"
            )

        year = match.group(1)
        code = match.group(2)

        # Year range check (optional - sanity check)
        year_int = int(year)
        if not (2020 <= year_int <= 2030):
            return False, None, f"Invalid year in invoice number: {year}"

        # Build normalized invoice number
        normalized = f"INV-{year}-{code}"

        return True, normalized, None

    @staticmethod
    def get_format_hint() -> str:
        """Get user-friendly format hint for input prompt."""
        return (
            "Expected format: <code>INV-YYYY-XXXXXX</code>\n"
            "Example: <code>INV-2025-ABC123</code>\n\n"
            "<i>YYYY = 4-digit year, XXXXXX = 6 alphanumeric characters</i>"
        )
```

### Phase 2: Database Layer

**File:** `repositories/order.py`

```python
@staticmethod
async def get_by_invoice_number(
    invoice_number: str,
    session: AsyncSession | Session
) -> Optional[int]:
    """
    Get order ID by exact invoice number match.

    SECURITY: Uses exact match (=) instead of LIKE to prevent SQL injection vectors.
    Input MUST be validated by InvoiceValidator before calling this method.

    Args:
        invoice_number: Normalized invoice number (e.g., "INV-2025-ABC123")
        session: Database session

    Returns:
        Order ID if found, None otherwise
    """
    from sqlalchemy import select
    from models.invoice import Invoice
    from models.order import Order

    # Query with exact match (secure - no wildcards)
    stmt = (
        select(Order.id)
        .join(Invoice, Invoice.order_id == Order.id)
        .where(Invoice.invoice_number == invoice_number)  # Exact match only
        .where(Invoice.is_active == True)  # Only active invoices
        .limit(1)
    )

    result = await session_execute(stmt, session)
    row = result.fetchone()

    return row[0] if row else None
```

### Phase 3: FSM State

**File:** `handlers/admin/admin_states.py`

Add new state class:

```python
class AdminOrderSearchStates(StatesGroup):
    waiting_for_invoice_id = State()
```

### Phase 4: Handler Logic

**File:** `handlers/admin/shipping_management.py`

#### 4a. Add Search Button (Level 0)

In `show_shipping_management_menu()`:

```python
# After filter change button
kb_builder.button(
    text="🔍 Search by Invoice ID",
    callback_data=ShippingManagementCallback.create(level=11)  # New level
)
```

#### 4b. Prompt for Invoice ID (Level 11)

```python
async def prompt_invoice_search(**kwargs):
    """
    Level 11: Prompt for Invoice ID Search

    Sets FSM state and shows text input prompt with format hint.
    """
    callback = kwargs.get("callback")
    state = kwargs.get("state")

    # Set FSM state
    from handlers.admin.admin_states import AdminOrderSearchStates
    await state.set_state(AdminOrderSearchStates.waiting_for_invoice_id)

    # Store current context for back navigation
    unpacked_cb = ShippingManagementCallback.unpack(callback.data)
    await state.update_data(
        previous_filter=unpacked_cb.filter_type,
        previous_page=unpacked_cb.page
    )

    # Build message with format hint
    from utils.invoice_validator import InvoiceValidator

    message_text = (
        "🔍 <b>Search Order by Invoice ID</b>\n\n"
        "Please enter the invoice number:\n\n"
        f"{InvoiceValidator.get_format_hint()}"
    )

    # Build keyboard
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=0)  # Back to menu
    )

    await callback.message.edit_text(text=message_text, reply_markup=kb_builder.as_markup())
```

#### 4c. Handle Text Input with Validation

Add new text handler in router section:

```python
@shipping_management_router.message(AdminOrderSearchStates.waiting_for_invoice_id)
async def handle_invoice_search_input(
    message: types.Message,
    session: AsyncSession | Session,
    state: FSMContext
):
    """
    Handle invoice ID text input from admin with format validation.
    """
    from repositories.order import OrderRepository
    from services.order_management import OrderManagementService
    from enums.bot_entity import BotEntity
    from utils.invoice_validator import InvoiceValidator

    search_term = message.text.strip()

    # STEP 1: Validate format (BEFORE database query)
    is_valid, normalized_invoice, error_msg = InvoiceValidator.validate(search_term)

    if not is_valid:
        # Invalid format - show error with hint
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text="🔍 Try Again",
            callback_data=ShippingManagementCallback.create(level=11)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=ShippingManagementCallback.create(level=0)
        )
        kb_builder.adjust(1)

        await message.answer(
            f"❌ <b>Invalid Format</b>\n\n{error_msg}",
            reply_markup=kb_builder.as_markup()
        )
        return

    # STEP 2: Search in database (only if format valid)
    order_id = await OrderRepository.get_by_invoice_number(normalized_invoice, session)

    # Clear FSM state
    await state.clear()

    # STEP 3: Handle results
    if not order_id:
        # Not found
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text="🔍 Try Again",
            callback_data=ShippingManagementCallback.create(level=11)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=ShippingManagementCallback.create(level=0)
        )
        kb_builder.adjust(1)

        await message.answer(
            f"❌ <b>Order Not Found</b>\n\n"
            f"No active order found for invoice: <code>{normalized_invoice}</code>\n\n"
            f"<i>Note: Cancelled orders are not shown.</i>",
            reply_markup=kb_builder.as_markup()
        )
        return

    # STEP 4: Show order detail
    try:
        msg, kb = await OrderManagementService.get_order_detail_view(
            order_id=order_id,
            session=session,
            entity=BotEntity.ADMIN,
            callback_factory=ShippingManagementCallback,
            filter_type=None,
            page=0
        )
        await message.answer(text=msg, reply_markup=kb.as_markup())
    except Exception as e:
        logging.error(f"Error loading order {order_id}: {e}")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=ShippingManagementCallback.create(level=0)
        )
        await message.answer(
            f"❌ <b>Error</b>\n\nFailed to load order details.",
            reply_markup=kb_builder.as_markup()
        )
```

#### 4d. Update Router

Add level 11 to navigation router:

```python
levels = {
    0: show_shipping_management_menu,
    1: show_order_list,
    2: show_order_detail,
    # ... existing levels ...
    10: show_filter_menu,
    11: prompt_invoice_search,  # NEW
}
```

### Phase 5: Localization

**Files:** `l10n/de.json`, `l10n/en.json`

Add keys:

```json
{
  "admin_order_search_title": "🔍 Search Order by Invoice ID",
  "admin_order_search_prompt": "Please enter the invoice number:",
  "admin_order_search_format_hint": "Expected format: INV-YYYY-XXXXXX",
  "admin_order_search_example": "Example: INV-2025-ABC123",
  "admin_order_search_invalid_format": "Invalid invoice format",
  "admin_order_search_not_found": "No active order found for invoice:",
  "admin_order_search_button": "🔍 Search by Invoice ID",
  "admin_order_search_try_again": "🔍 Try Again",
  "admin_order_search_cancelled_note": "Note: Cancelled orders are not shown."
}
```

## Security Considerations

### 1. Input Validation (Defense in Depth)

**Format Constraint:** `INV-YYYY-XXXXXX`
- Prevents arbitrary SQL input
- Limits attack surface to known format
- Rejects malformed inputs immediately

**Validation Steps:**
1. Regex validation BEFORE database query
2. Length check (max 50 chars to prevent buffer attacks)
3. Year range check (2020-2030 sanity check)
4. Normalize to uppercase (consistent format)

**Rejected Inputs:**
- `' OR 1=1 --` (SQL injection attempt)
- `INV-2025-ABC123'; DROP TABLE orders;--` (SQL injection)
- `../../../etc/passwd` (path traversal)
- `<script>alert('xss')</script>` (XSS attempt)
- Any input not matching `^INV-\d{4}-[A-Z0-9]{6}$`

### 2. Database Query Security

**Exact Match Only:**
- Use `WHERE invoice_number = ?` (exact match)
- NO LIKE queries (no wildcards = no injection vectors)
- SQLAlchemy parameterized queries (built-in escaping)

**Example Safe Query:**
```sql
SELECT order_id FROM invoices
WHERE invoice_number = 'INV-2025-ABC123'
  AND is_active = TRUE
LIMIT 1
```

### 3. Authorization

- Only admins can access search (existing `IsAdminFilter`)
- No user-facing exposure of this feature

### 4. Rate Limiting (Future Enhancement)

Consider adding rate limiting if search is abused:
- Max 10 searches per minute per admin
- Track via Redis counter

## Testing Checklist

### Valid Inputs

- [ ] `INV-2025-ABC123` (standard format)
- [ ] `inv-2025-abc123` (lowercase - should normalize)
- [ ] `  INV-2025-ABC123  ` (with whitespace - should trim)
- [ ] `INV-2025-123456` (all numeric code)
- [ ] `INV-2025-ABCDEF` (all alpha code)

### Invalid Inputs (Should be REJECTED)

- [ ] `INV-2025-ABC12` (too short - 5 chars instead of 6)
- [ ] `INV-2025-ABC1234` (too long - 7 chars instead of 6)
- [ ] `INV-25-ABC123` (year too short - 2 digits instead of 4)
- [ ] `INV-20250-ABC123` (year too long - 5 digits)
- [ ] `INVOICE-2025-ABC123` (wrong prefix)
- [ ] `INV-2025-ABC-123` (extra hyphen)
- [ ] `INV-2025-ABC 123` (space in code)
- [ ] `INV-2025-` (missing code)
- [ ] `ABC123` (no prefix/year)
- [ ] `' OR 1=1 --` (SQL injection)
- [ ] `<script>alert(1)</script>` (XSS)
- [ ] Empty string
- [ ] 1000 characters long (excessive length)

### Database Tests

- [ ] Search existing invoice (found)
- [ ] Search non-existent invoice (not found)
- [ ] Search cancelled invoice (should not appear - is_active=False)
- [ ] Search with multiple invoices for same order (should return order once)

### UI/UX Tests

- [ ] Error message shows format hint
- [ ] "Try Again" button works
- [ ] "Back" button returns to shipping menu
- [ ] Order detail view displays correctly
- [ ] FSM state cleared after search

## Performance Considerations

1. **Database Index**: Ensure `invoice_number` column has UNIQUE index
   - Check: `CREATE UNIQUE INDEX idx_invoice_number ON invoices(invoice_number);`
   - Exact match queries are O(1) with index

2. **No LIKE Queries**: Exact match is faster and more secure than pattern matching

3. **Single Query**: One SELECT with JOIN instead of multiple queries

## Migration Notes

**No database migration required** - uses existing tables and columns.

**Optional Performance Enhancement:**
If `invoice_number` doesn't have a unique index yet, add it:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_number
ON invoices(invoice_number);
```

## Rollout Plan

1. Implement `InvoiceValidator` utility class
2. Add `get_by_invoice_number()` repository method
3. Add FSM state and handlers
4. Add button to shipping management menu
5. Test thoroughly with invalid inputs
6. Deploy to staging
7. Validate with admin users
8. Deploy to production
9. Monitor search usage and error rates

## Future Enhancements (Out of Scope)

- Search by user telegram_id or username (separate feature)
- Search history (recent searches)
- Autocomplete suggestions (requires UI changes)
- Bulk search (CSV upload)

## Related Files

**New Files:**
- `utils/invoice_validator.py`

**Modified Files:**
- `handlers/admin/admin_states.py` (add FSM state)
- `handlers/admin/shipping_management.py` (add handlers and router level)
- `repositories/order.py` (add search method)
- `l10n/de.json` (add localization keys)
- `l10n/en.json` (add localization keys)

## Notes

- Invoice format is system-wide standard: `INV-YYYY-XXXXXX`
- Year range 2020-2030 is sanity check (adjust as needed)
- Validation happens client-side (in handler) before DB query
- Only active invoices are searchable (cancelled orders excluded)
- Search is admin-only feature (no user access)