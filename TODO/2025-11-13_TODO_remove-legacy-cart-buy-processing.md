# Remove Legacy Cart Buy Processing Method

**Date:** 2025-11-13
**Priority:** Low
**Estimated Effort:** Low (30 minutes)

---

## Description
Remove the legacy `CartService.buy_processing()` method that is no longer used after the invoice-based checkout system refactoring. This method was part of the old direct purchase flow and has been replaced by the Order domain.

## Context
After PR #47 (cart service refactoring), the cart handler routing no longer includes `buy_processing()`:

**Current Routing (handlers/user/cart.py:306-312):**
```python
levels = {
    0: show_cart,
    1: delete_cart_item_confirm,
    2: checkout_processing,
    3: create_order_handler,  # Redirects to Order domain
    4: delete_cart_item_execute,
}
```

The `buy_processing()` method exists in `services/cart.py:635` but is **never called**.

## Acceptance Criteria
- [ ] Remove `CartService.buy_processing()` method from `services/cart.py`
- [ ] Remove any related tests (if they exist)
- [ ] Verify all cart tests still pass
- [ ] Ensure no other code references this method

## Technical Implementation

### Files to Modify
1. **services/cart.py**
   - Remove method at line 635: `async def buy_processing(...)`
   - Remove entire implementation (approximately 50-100 lines)

2. **tests/cart/** (if applicable)
   - Search for tests referencing `buy_processing`
   - Remove obsolete test cases

### Verification Steps
```bash
# Search for any remaining references
grep -r "buy_processing" handlers/ services/ tests/

# Run cart tests
python -m pytest tests/cart/unit/test_cart_service_crud.py -v

# Verify routing still works
python -m pytest tests/cart/integration/ -v  # If integration tests exist
```

## Impact
- **Risk:** Low - method is unused
- **Breaking Changes:** None - method already removed from routing
- **Benefits:**
  - Cleaner codebase
  - Removes confusion about which purchase flow to use
  - Reduces maintenance burden

## Related
- PR #47: Cart service refactoring
- Invoice-based checkout system (OrderCallback Level 0)
- `handlers/user/order.py:create_order()` - current implementation
