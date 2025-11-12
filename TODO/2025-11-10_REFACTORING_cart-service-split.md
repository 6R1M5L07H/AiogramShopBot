# TODO: Refactoring - Split CartService and Extract UI Logic to Handlers

**Status:** Planned
**Priority:** High
**Created:** 2025-11-10
**Estimated Effort:** 6-8 hours

## Problem

`services/cart.py` has grown to **1210 lines with 34 methods**, violating the Single Responsibility Principle:

**Current Issues:**
1. **Mixed Responsibilities:** Cart, Checkout, Order Display, and Legacy Buy logic all mixed together
2. **UI in Services:** Services return `tuple[str, InlineKeyboardBuilder]` - coupling to Telegram UI
3. **Not Testable:** Can't test business logic without mocking Telegram objects
4. **Unclear Boundaries:** Hard to understand what each method does

## Architecture Principle: Hybrid Approach (Pragmatic)

### Services Responsibility
- ✅ Business logic (validation, calculations)
- ✅ Data retrieval (via repositories)
- ✅ **Message formatting** (return plain HTML string)
- ❌ **NO Telegram objects** (`InlineKeyboardBuilder`, `CallbackQuery`, `Message`)

### Handlers Responsibility
- ✅ Call services for data/messages
- ✅ **Build UI** (`InlineKeyboardBuilder`, button creation)
- ✅ Telegram API calls (`edit_text`, `send_message`)

**Why this works:**
- Services are **testable** (pure data in/out, no UI coupling)
- Message formatting stays **centralized** (no duplication)
- Handlers stay **thin** (mostly UI assembly)

---

## Goal: 4 Focused Services + Handler Refactoring

### 1. CartService (~150 lines) - Cart Business Logic

**Responsibility:** Cart data management and validation

**Methods to keep/refactor:**
- `add_to_cart(user_id, item, quantity) -> bool` - Add item with stock validation
- `remove_from_cart(cart_item_id) -> bool` - Remove cart item
- `get_cart_summary(user_id) -> CartSummaryDTO` - Get cart data for display
- `get_cart_items(user_id) -> list[CartItemDTO]` - Get all cart items
- `validate_cart_stock(user_id) -> list[OutOfStockItem]` - Check stock before checkout
- `clear_cart(user_id)` - Clear all cart items

**Returns:** DTOs, booleans, data objects
**NO:** Formatted messages, keyboards

---

### 2. CartCheckoutService (~400 lines) - Checkout Orchestration

**Responsibility:** Checkout flow coordination, order creation, payment setup

**Methods to move/refactor:**
- `get_checkout_summary_message(cart_items) -> str` - Format checkout message (HTML string)
- `create_order_and_reserve_items(user_id, cart_items) -> OrderCreationResult` - Order + stock reservation
- `check_shipping_address_required(cart_items) -> bool` - Validate if address needed
- `check_pending_order_exists(user_id) -> Order | None` - Check for pending orders
- `handle_wallet_only_payment(user_id, cart_items) -> PaymentResult` - Wallet-only payment flow
- `create_order_with_crypto(user_id, order_id, crypto) -> InvoiceResult` - Finalize order with crypto
- `validate_stock_before_checkout(cart_items) -> StockValidationResult` - Stock check
- `calculate_cart_totals(cart_items) -> CartTotals` - Calculate items + shipping

**Returns:** DTOs, data objects, formatted strings (for messages)
**NO:** InlineKeyboardBuilder

**Note:** Wallet-only flow creates full Order with Invoice "INV-2025-123456" (legal invoice), immediately marked as PAID.

---

### 3. OrderDisplayService (~300 lines) - Order Message Formatting

**Responsibility:** Format order/invoice data for display (message strings only)

**Methods to move/refactor:**
- `get_pending_order_message(order_id) -> str` - Format pending order message (HTML)
- `get_payment_screen_message(order_id, invoice_id) -> str` - Format payment details (HTML)
- `get_stock_adjustment_message(order_id, adjustments) -> str` - Format stock adjustment info (HTML)
- `get_order_expired_message(order_id) -> str` - Format order expired message (HTML)

**Returns:** HTML strings (formatted messages)
**NO:** InlineKeyboardBuilder

---

### 4. LegacyBuyService (~100 lines) - Legacy Direct Wallet Purchase

**Responsibility:** Old direct wallet purchase flow (bypasses Order system entirely)

**Methods to move:**
- `buy_processing(user_id, cart_items) -> BuyResult` - Legacy direct wallet purchase

**Status:** ⚠️ **Deprecated** - To be replaced by regular Order flow (wallet-only)

**Why deprecated:**
- Old flow: Cart → Direct Buy → Deduct Wallet → Create Buy records (no Order, no Invoice)
- New flow: Cart → Order (wallet-only) → Invoice "INV-2025-..." → Mark PAID → Complete
- New flow provides: Order tracking, Invoice records, unified payment handling

**Migration strategy:** Replace all `buy_processing()` calls with `handle_wallet_only_payment()` from CartCheckoutService.

---

### 5. Handlers Refactoring (handlers/user/cart.py + order.py)

**Move FROM services TO handlers:**
- All `InlineKeyboardBuilder` creation
- All button text/callback assembly
- All `CallbackQuery`/`Message` handling

**Example - BEFORE (Bad):**
```python
# services/cart.py
async def create_buttons(message, session) -> tuple[str, InlineKeyboardBuilder]:
    msg = "Your cart..."
    kb = InlineKeyboardBuilder()  # ❌ UI in Service
    kb.button(text="Checkout", callback_data=...)
    return msg, kb
```

**Example - AFTER (Good):**
```python
# services/cart.py
async def get_cart_summary_message(user_id: int, session) -> str:
    cart_items = await CartItemRepository.get_all_by_user_id(user_id, session)
    message = "Your cart:\n"
    for item in cart_items:
        message += f"- {item.name} x{item.quantity}\n"
    return message  # ✅ String only

# handlers/user/cart.py
async def show_cart(callback: CallbackQuery, session):
    user_id = callback.from_user.id
    message = await CartService.get_cart_summary_message(user_id, session)

    # ✅ UI Logic in Handler
    kb = InlineKeyboardBuilder()
    kb.button(text=Localizator.get_text("checkout"), callback_data=CartCallback.create(2))
    kb.button(text=Localizator.get_text("clear_cart"), callback_data=CartCallback.create(99))

    await callback.message.edit_text(message, reply_markup=kb.as_markup())
```

---

## Payment System Architecture (Context)

### Two Parallel Flows (Both Permanent)

**1. Order Flow** (Item purchases)
- User buys items from catalog (digital/physical)
- Payment: Wallet balance + Cryptocurrency
- **Legal Invoice:** "INV-2025-123456"
- Order tracking, shipping address (physical items), strike system
- Example: User buys 3x USB sticks for €90, pays €20 from wallet + €70 BTC

**2. Wallet Top-Up Flow** (Balance reload)
- User reloads wallet balance
- Payment: Cryptocurrency only
- **Technical Reference:** "TOPUP-2025-ABCDEF" (NOT a legal invoice)
- No order, no shipping, no strikes
- Example: User adds €100 to wallet via BTC

**Legacy Buy Flow** (To be removed)
- Direct wallet purchase bypassing Order system
- Creates Buy records but no Order/Invoice
- Should be replaced by Order flow (wallet-only variant)

---

## Implementation Steps

### Phase 1: Create New Services (No Breaking Changes)
1. ✅ Create `services/cart_shipping.py` - Shipping calculation logic
2. Create `services/order_display.py` - Order message formatting
3. Create `services/cart_checkout.py` - Checkout orchestration
4. Create `services/legacy_buy.py` - Legacy buy flow
5. Refactor each service to return **data/strings only** (no InlineKeyboardBuilder)

### Phase 2: Refactor Handlers
1. Move all `InlineKeyboardBuilder` logic from services to handlers
2. Update handlers to call refactored services
3. Update handler imports

Files to update:
- `handlers/user/cart.py` - Cart display, checkout initiation
- `handlers/user/order.py` - Order display, payment screens
- `handlers/admin/*` - If any admin handlers use cart services

### Phase 3: Slim Down CartService
1. Remove order display methods → `OrderDisplayService`
2. Remove checkout methods → `CartCheckoutService`
3. Remove legacy buy → `LegacyBuyService`
4. Keep only pure cart CRUD operations

### Phase 4: Testing
1. Write unit tests for each service (now testable without Telegram mocks!)
2. Integration tests for handler flows
3. Smoke test all user flows

### Phase 5: Cleanup
1. Delete old code from `services/cart.py`
2. Remove legacy buy flow entirely (replace with Order flow)
3. Update documentation
4. Final code review

---

## Testing Strategy

### Services (Unit Tests - Easy Now!)
```python
# tests/services/test_cart_service.py
async def test_get_cart_summary_message():
    # ✅ No Telegram mocks needed!
    message = await CartService.get_cart_summary_message(user_id=1, session=mock_session)
    assert "Total: 123.45" in message
    assert "Item A" in message
```

### Handlers (Integration Tests)
```python
# tests/handlers/test_cart_handler.py
async def test_show_cart_handler():
    # Test full flow with mocked Telegram objects
    callback = mock_callback_query()
    await cart_handler.show_cart(callback, session)
    assert callback.message.edit_text.called
```

---

## Benefits

✅ **Testability:** Services return strings/DTOs - no Telegram coupling
✅ **Single Responsibility:** Each service has one clear purpose
✅ **Maintainability:** Smaller files (~150-400 lines each)
✅ **Clear Boundaries:** Services = Logic, Handlers = UI
✅ **Parallel Development:** Multiple devs can work on different services
✅ **Reduced Merge Conflicts:** Changes isolated to specific services

---

## File Structure After Refactoring

```
services/
├── cart.py (~150 lines)              # Cart CRUD operations
├── cart_checkout.py (~400 lines)     # Checkout orchestration
├── cart_shipping.py (~100 lines)     # Shipping calculation (already created)
├── order_display.py (~300 lines)     # Order message formatting
├── legacy_buy.py (~100 lines)        # Legacy buy flow (to be removed)
└── order.py (unchanged)              # Order orchestration

handlers/user/
├── cart.py (refactored)              # Cart UI + button building
└── order.py (refactored)             # Order UI + button building
```

---

## Dependencies

**Blocked by:** None
**Blocks:**
- Future cart features (easier to add in focused services)
- Legacy buy removal (needs separate service first for clean migration)
- Full test coverage (services now testable)

---

## Notes

- Keep `services/cart_shipping.py` separate (shipping calculation logic)
- `InvoiceFormatterService` stays as-is (already focused)
- All new services use dual-mode session pattern (`AsyncSession | Session`)
- Follow repository pattern: Services → Repositories → Models
- **Critical:** Ensure backward compatibility during migration (no breaking changes)
- **Invoice Types:** "INV-..." (legal, for orders) vs "TOPUP-..." (technical, for wallet reloads)

---

## Related Files

- `services/cart.py` (to be split)
- `handlers/user/cart.py` (needs UI logic migration)
- `handlers/user/order.py` (needs UI logic migration)
- `services/order.py` (orchestration, keep as-is)
- `services/invoice_formatter.py` (used by OrderDisplayService)
- `tests/services/test_cart_service.py` (new tests to add)

---

## Success Criteria

- [ ] All services return data/strings (no `InlineKeyboardBuilder`)
- [ ] All button building happens in handlers
- [ ] `services/cart.py` reduced to ~150 lines
- [ ] Unit tests written for all new services
- [ ] All existing user flows still work (manual smoke test)
- [ ] No Telegram objects in service signatures
- [ ] Legacy buy flow removed, replaced by Order flow (wallet-only)