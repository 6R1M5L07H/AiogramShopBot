# Software Engineering Audit & Code Quality Improvements

**Date:** 2025-11-01
**Updated:** 2025-11-02
**Priority:** Medium-High
**Status:** In Progress (3/11 Issues Completed, 2 Skipped)
**Estimated Effort:** 6-10 hours (incremental)
**Branch:** `technical-debt`

---

## Overview

Comprehensive code quality audit focusing on:
- Code duplication
- Refactoring opportunities
- Design patterns
- Maintainability improvements
- Technical debt reduction

---

## Identified Issues

### 1. Duplicate Code: Invoice/Order Formatting ✅ COMPLETED

**Priority:** HIGH
**Effort:** 2-3 hours → Actual: 4 hours
**Status:** ✅ Completed (2025-11-02)
**Commit:** 33c0f43 - refactor: complete invoice formatter refactoring with master template

**Resolution:**

✅ **Created Master Template** (`services/invoice_formatter.py`)
- `format_complete_order_view()` - 380 lines master template
- Supports 6 view types: admin_order, payment_screen, wallet_payment, cancellation_refund, admin_cancellation, purchase_history
- Unified items structure with private_data support

✅ **Refactored 6 Locations:**
1. `services/order.py::_format_payment_screen` (80→28 lines, 65% reduction)
2. `services/order.py::_format_wallet_payment_invoice` (70→26 lines, 63% reduction)
3. `services/notification.py::build_order_cancelled_wallet_refund_message` (165→24 lines, 85% reduction)
4. `services/notification.py::build_order_cancelled_by_admin_message` (95→59 lines, 38% reduction)
5. `services/buy.py::get_purchase` (95→45 lines, 53% reduction)
6. `handlers/admin/shipping_management.py::show_order_details` (already done in earlier commit)

**Results:**
- Total code reduction: 546→194 lines (64% less caller code)
- Eliminated 352 lines of duplicate formatting logic
- Bug fixes now require changes in 1 location instead of 6
- Single source of truth for invoice formatting

---

### 2. Duplicate Code: Crypto Button Generation ✅ COMPLETED

**Priority:** MEDIUM
**Effort:** 30-45 minutes
**Status:** ✅ Completed (2025-11-02)
**Previous TODO:** 2025-10-24_TODO_refactor-crypto-button-generation.md

**Resolution:**

✅ **Added enum methods to Cryptocurrency:**
- `get_localization_key()` - Returns (BotEntity, key) tuple for button text
- `get_payment_options()` - Returns list of available cryptocurrencies in display order

✅ **Refactored button generation** (2 locations):
- `services/cart.py:_show_crypto_selection_screen()` - 32 lines → 7 lines (78% reduction)
- `services/user.py:get_top_up_buttons()` - 20 lines → 8 lines (60% reduction)

✅ **Benefits:**
- Adding new crypto: Only update enum, buttons auto-generated
- Consistent order across all screens
- Wallet top-up now supports USDT/USDC (was missing before)

**Before (32 lines):**
```python
kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "btc_top_up"), ...)
kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "eth_top_up"), ...)
# ... 6 more identical blocks
```

**After (5 lines):**
```python
for crypto in Cryptocurrency.get_payment_options():
    entity, key = crypto.get_localization_key()
    kb_builder.button(text=Localizator.get_text(entity, key), ...)
```

---

### 3. Duplicate Code: Keyboard Builder Patterns ⏭️ SKIPPED

**Priority:** MEDIUM
**Effort:** 2-3 hours
**Status:** ⏭️ Skipped (2025-11-02) - Low ROI

**Analysis:**
- Found 88 InlineKeyboardBuilder() instances (16 handlers + 72 services)
- Most keyboards are highly specific with different:
  - Button counts and texts
  - Callback factories and parameters
  - Layouts (1/2/mixed columns)
  - Dynamic generation (DB loops)

**Decision:** SKIP
- Keyboards too specific for generic utils
- ROI too low (~20-30 lines savings / 88 locations = 0.3 lines/location)
- Would reduce readability (abstraction without benefit)
- Better to leave inline for clarity

**Recommendation:**
Leave keyboard building as-is. The pattern is simple enough and varies too much for useful abstraction.

---

### 4. Duplicate Code: User Permission Checks

**Priority:** LOW
**Effort:** 1-2 hours

**Issue:**
Admin verification scattered across codebase:
```python
# Pattern 1 (old, deprecated):
if message.from_user.id in config.ADMIN_ID_LIST:
    ...

# Pattern 2 (new, secure):
if config.ADMIN_ID_HASHES:
    from utils.admin_hash_generator import verify_admin_id
    is_admin = verify_admin_id(telegram_id, config.ADMIN_ID_HASHES)
else:
    is_admin = telegram_id in config.ADMIN_ID_LIST
```

**Locations:**
```
run.py:60
bot.py:56
multibot.py (similar pattern)
+ scattered across handlers
```

**Solution:**
Create `utils/permission_utils.py`:
```python
def is_admin_user(telegram_id: int) -> bool:
    """Check if user is admin using secure hash-based verification."""
    if config.ADMIN_ID_HASHES:
        from utils.admin_hash_generator import verify_admin_id
        return verify_admin_id(telegram_id, config.ADMIN_ID_HASHES)
    return telegram_id in config.ADMIN_ID_LIST

def is_banned_user(telegram_id: int, session: AsyncSession) -> bool:
    """Check if user is banned."""
    # Centralized ban check
    pass
```

---

### 5. Inconsistent Error Handling

**Priority:** MEDIUM
**Effort:** 3-4 hours

**Issue:**
Inconsistent exception handling patterns:
- Some functions return None on error
- Some raise exceptions
- Some log and continue
- Some log and re-raise

**Examples:**
```python
# Pattern A: Return None
def some_function():
    try:
        ...
    except Exception as e:
        logging.error(f"Error: {e}")
        return None

# Pattern B: Re-raise
def other_function():
    try:
        ...
    except Exception as e:
        logging.error(f"Error: {e}")
        raise

# Pattern C: Swallow exception
def another_function():
    try:
        ...
    except Exception as e:
        logging.error(f"Error: {e}")
        pass
```

**Solution:**
Define error handling strategy:
1. **Services**: Raise custom exceptions
2. **Handlers**: Catch and show user-friendly messages
3. **Repositories**: Let SQLAlchemy exceptions bubble up
4. **Jobs**: Log and continue (don't crash scheduler)

Create `exceptions/` directory with custom exceptions:
```python
class OrderException(Exception):
    """Base exception for order-related errors."""
    pass

class InsufficientStockException(OrderException):
    """Raised when item stock insufficient."""
    pass

class PaymentException(Exception):
    """Base exception for payment-related errors."""
    pass
```

---

### 6. Missing Type Hints

**Priority:** LOW
**Effort:** 4-6 hours (incremental)

**Issue:**
Many functions lack type hints:
```python
# Current (no hints):
def process_payment(order_id, amount):
    ...

# Better:
def process_payment(order_id: int, amount: float) -> bool:
    ...
```

**Benefits:**
- Better IDE autocomplete
- Catch type errors early
- Self-documenting code

**Strategy:**
Add type hints incrementally:
1. Start with services/ (core logic)
2. Then repositories/ (data layer)
3. Then handlers/ (UI layer)
4. Use mypy for validation

---

### 7. Long Functions (God Functions)

**Priority:** MEDIUM
**Effort:** 3-4 hours

**Issue:**
Some functions exceed 100-200 lines:
```
services/order.py:create_order()          # ~150 lines
services/order.py:process_payment()       # ~120 lines
handlers/admin/shipping_management.py:show_order_details()  # ~100 lines
```

**Solution:**
Extract smaller functions:
```python
# Before:
def create_order(...):  # 150 lines
    # Validate cart
    # Check stock
    # Reserve items
    # Calculate totals
    # Create order
    # Handle physical items
    # Handle wallet payment
    # Send notifications

# After:
def create_order(...):  # 30 lines
    cart_items = _validate_and_get_cart_items(...)
    stock_adjustments = _reserve_stock(cart_items)
    totals = _calculate_order_totals(cart_items, wallet_balance)
    order = _create_order_record(...)

    if has_physical_items:
        _request_shipping_address(...)

    if wallet_covers_full_amount:
        _process_wallet_payment(...)

    return order
```

---

### 8. Magic Numbers and Strings ⏭️ SKIPPED

**Priority:** LOW
**Effort:** 1-2 hours
**Status:** ⏭️ Skipped (2025-11-02) - Low Impact

**Analysis:**
- Callback levels already have inline comments explaining meaning
- Status codes use OrderStatus enum (not string comparison)
- Config limits already documented

**Decision:** SKIP
- Comments already provide clarity: `# Level 4 = Cancel Order`
- Creating callback level enums would add complexity without benefit
- No actual bugs or maintainability issues found
- Time better spent on higher-impact issues

**Recommendation:**
Keep current approach. Inline comments are sufficient for callback level documentation.

---

### 9. Database Query N+1 Problems

**Priority:** MEDIUM
**Effort:** 2-3 hours

**Issue:**
Potential N+1 queries in loops:
```python
# Anti-pattern:
for order in orders:
    user = await UserRepository.get_user_by_id(order.user_id)  # N queries!
    print(f"Order for {user.telegram_username}")
```

**Solution:**
Use SQLAlchemy eager loading:
```python
# Better:
orders = await session.execute(
    select(Order).options(selectinload(Order.user))
)
```

**Locations to check:**
```
repositories/order.py
handlers/admin/shipping_management.py:get_pending_orders()
handlers/admin/user_management.py:show_users()
```

---

### 10. Inconsistent Naming Conventions

**Priority:** LOW
**Effort:** Covered in Security Audit Finding 6

**Issue:**
Mixed naming styles:
```python
# camelCase (JavaScript style)
cartItem.py
orderItem.py

# snake_case (Python style)
user_strike.py
payment_transaction.py
```

**Solution:**
Standardize to Python conventions (snake_case).

---

### 11. Handler/Service Layer Violation (Separation of Concerns) ✅ COMPLETED

**Priority:** HIGH
**Effort:** 4-6 hours
**Status:** ✅ Completed (2025-11-02)

**Issue:**
Handlers directly calling Repositories instead of going through Services:
- Violates layered architecture
- Makes testing harder
- Duplicates business logic
- Bypasses service-layer validation

**Architecture Should Be:**
```
Handler → Service → Repository → Database
```

**Resolution:**

✅ **handlers/admin/shipping_management.py** - REFACTORED
- Created ShippingService with 6 new methods
- Eliminated all 17 direct repository calls
- Added proper error handling for missing orders
- Added 4 automated tests with aiogram-tests framework
- Commit: `02a5690 - feat: refactor shipping management with service layer separation`

✅ **handlers/admin/user_management.py** - VERIFIED CLEAN
- All calls through AdminService and BuyService
- No violations found

✅ **handlers/admin/inventory_management.py** - VERIFIED CLEAN
- All calls through AdminService and ItemService
- No violations found

✅ **handlers/user/order.py** - VERIFIED CLEAN
- All calls through OrderService
- No violations found

**Outcome:**
All handlers now follow proper service layer pattern. No handler/repository violations remain in codebase.

**Solution:**
Move logic to services:
```python
# Before (Handler directly calling Repository):
async def show_pending_orders(**kwargs):
    session = kwargs.get("session")
    orders = await OrderRepository.get_orders_awaiting_shipment(session)
    # ... build message ...

# After (Handler calling Service):
async def show_pending_orders(**kwargs):
    session = kwargs.get("session")
    msg, kb = await ShippingService.get_pending_orders_view(session)
    await callback.message.edit_text(msg, reply_markup=kb.as_markup())

# Service handles all logic:
class ShippingService:
    @staticmethod
    async def get_pending_orders_view(session):
        orders = await OrderRepository.get_orders_awaiting_shipment(session)
        # Business logic here
        message_text = _build_orders_list(orders)
        keyboard = _build_orders_keyboard(orders)
        return message_text, keyboard
```

**Benefits:**
- ✅ Clear separation of concerns
- ✅ Handler only handles UI/routing
- ✅ Service contains business logic
- ✅ Easier to test (mock services, not repositories)
- ✅ Reusable logic (API endpoints can use same services)

**Testing Impact:**
```python
# Before: Hard to test (need database)
async def test_show_orders():
    # Need real database, session, etc.
    result = await show_pending_orders(session=db_session)

# After: Easy to test (mock service)
async def test_show_orders():
    mock_service = Mock(return_value=("Test message", keyboard))
    result = await show_pending_orders(service=mock_service)
```

---

## Prioritized Implementation Plan

### Phase 1: Architecture & High-Impact Refactoring (8-10 hours)
1. **🔥 Handler/Service Separation (4-6h)** - **CRITICAL** - Fix layering violations
2. ✅ Invoice Formatter (2-3h) - **Highest ROI** - Eliminate duplicate code
3. ✅ Crypto Button Generation (30-45min) - **Quick win**
4. ✅ Keyboard Builder Utils (2-3h) - **Widely applicable**

### Phase 2: Error Handling & Type Safety (6-8 hours)
5. Custom Exception Classes (2h)
6. Type Hints for Services (2-3h)
7. Consistent Error Handling (3-4h)

### Phase 3: Code Organization (4-6 hours)
8. Extract Long Functions (3-4h)
9. Magic Numbers → Constants (1-2h)
10. Permission Utils (1-2h)

### Phase 4: Performance & Best Practices (2-3 hours)
11. N+1 Query Optimization (2-3h)

---

## Tooling & Automation

### Code Quality Tools

**Install:**
```bash
pip install pylint mypy black isort flake8
```

**1. Pylint** - Code quality checker
```bash
pylint services/ handlers/ repositories/
```

**2. MyPy** - Type checking
```bash
mypy --strict services/
```

**3. Black** - Code formatter
```bash
black .
```

**4. Isort** - Import sorting
```bash
isort .
```

**5. Flake8** - Style guide enforcement
```bash
flake8 --max-line-length=120 .
```

### Pre-commit Hooks

**File:** `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120']

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Install:**
```bash
pip install pre-commit
pre-commit install
```

---

## Metrics & KPIs

### Before Refactoring
- **Duplicate Code:** ~500+ lines duplicated
- **Average Function Length:** 60 lines
- **Type Hint Coverage:** ~20%
- **Pylint Score:** TBD
- **Code Complexity:** High (nested ifs, long functions)

### After Refactoring (Target)
- **Duplicate Code:** < 50 lines
- **Average Function Length:** 30 lines
- **Type Hint Coverage:** > 80%
- **Pylint Score:** > 8.0/10
- **Code Complexity:** Medium (extracted functions, clear flow)

---

## Testing Strategy

### For Each Refactoring:
1. **Before:** Run existing tests (manual or automated)
2. **During:** Keep behavior identical (no new features)
3. **After:** Verify all tests still pass

### Manual Testing Checklist:
- [ ] User can create orders (digital + physical)
- [ ] Admin can view order details
- [ ] Payment screens display correctly
- [ ] Notifications sent correctly
- [ ] Cart operations work
- [ ] Admin menu navigation works

---

## Related TODOs

- ✅ 2025-11-01_TODO_invoice-formatter-refactoring.md
- ✅ 2025-10-24_TODO_refactor-crypto-button-generation.md
- Security Audit Finding 6: Naming Conventions
- Security Audit Finding 7: Environment Templates

---

## Success Criteria

### Code Quality
- ✅ Pylint score > 8.0
- ✅ No critical code smells
- ✅ Type hints on all public functions
- ✅ < 10% duplicate code

### Maintainability
- ✅ New features easier to add
- ✅ Bug fixes require fewer file changes
- ✅ Onboarding easier for new developers

### Performance
- ✅ No N+1 queries
- ✅ No regression in response times

---

## Implementation Notes

### Best Practices
1. **One refactoring at a time** - Don't mix multiple changes
2. **Keep commits small** - Easy to review and revert
3. **Test after each change** - Catch regressions immediately
4. **Document decisions** - Why certain patterns chosen

### Avoid
- ❌ Premature optimization
- ❌ Over-engineering
- ❌ Changing behavior while refactoring
- ❌ Mixing refactoring with new features

---

**Status:** Ready for Implementation
**Next Step:** Start with Phase 1 (Invoice Formatter + Crypto Buttons)
