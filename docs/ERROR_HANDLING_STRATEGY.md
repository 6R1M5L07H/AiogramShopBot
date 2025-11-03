# Error Handling Strategy

**Date:** 2025-11-03
**Status:** Implemented
**Related:** TODO/2025-11-01_TODO_software-engineering-audit.md (Issue 5)

---

## Overview

This document defines the consistent error handling strategy used throughout the AiogramShopBot codebase.

---

## Exception Hierarchy

All custom exceptions inherit from `ShopBotException`:

```
ShopBotException (base)
├── OrderException
│   ├── OrderNotFoundException
│   ├── InsufficientStockException
│   ├── OrderExpiredException
│   ├── OrderAlreadyCancelledException
│   └── InvalidOrderStateException
├── PaymentException
│   ├── PaymentNotFoundException
│   ├── InvalidPaymentAmountException
│   ├── PaymentAlreadyProcessedException
│   └── CryptocurrencyNotSelectedException
├── ItemException
│   ├── ItemNotFoundException
│   ├── ItemAlreadySoldException
│   └── InvalidItemDataException
├── CartException
│   ├── EmptyCartException
│   ├── CartItemNotFoundException
│   └── InvalidCartStateException
├── UserException
│   ├── UserNotFoundException
│   ├── UserBannedException
│   └── InsufficientBalanceException
└── ShippingException
    ├── MissingShippingAddressException
    └── InvalidAddressException
```

---

## Layer-Specific Error Handling

### 1. Repository Layer

**Strategy:** Let SQLAlchemy exceptions bubble up

```python
# repositories/order.py
async def get_by_id(order_id: int, session):
    """Get order by ID. Raises SQLAlchemy exceptions on DB errors."""
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()
```

**Rationale:**
- Repositories are data access only
- Don't catch/transform DB exceptions here
- Service layer decides how to handle

---

### 2. Service Layer

**Strategy:** Raise custom exceptions

```python
# services/order.py
from exceptions.order import OrderNotFoundException

async def get_order(order_id: int, session):
    """
    Get order by ID.

    Raises:
        OrderNotFoundException: If order not found
    """
    order = await OrderRepository.get_by_id(order_id, session)
    if not order:
        raise OrderNotFoundException(order_id)
    return order
```

**Rationale:**
- Services contain business logic
- Custom exceptions provide context (entity IDs, states)
- Type-safe error handling
- Clear API contracts via docstrings

**Rules:**
-  Use specific exceptions (OrderNotFoundException, not ValueError)
-  Include entity IDs and relevant context
-  Document exceptions in docstrings
-  Don't catch and log without re-raising (hides errors)
-  Don't return None on error (ambiguous)

---

### 3. Handler Layer

**Strategy:** Catch and display user-friendly messages

```python
# handlers/user/order.py
from exceptions.order import OrderNotFoundException

async def show_order_details(callback: CallbackQuery, **kwargs):
    """Display order details."""
    try:
        session = kwargs['session']
        order = await OrderService.get_order(order_id, session)
        # ... build message ...
    except OrderNotFoundException:
        await callback.answer(
            " Order not found",
            show_alert=True
        )
        return
    except ShopBotException as e:
        # Catch all bot exceptions
        await callback.answer(
            f" Error: {str(e)}",
            show_alert=True
        )
        return
```

**Rationale:**
- Handlers are UI layer
- Convert technical exceptions to user-friendly messages
- Don't expose implementation details

**Rules:**
-  Catch specific exceptions first (OrderNotFoundException)
-  Catch ShopBotException as fallback
-  Show user-friendly messages
-  Log unexpected errors
-  Don't let exceptions crash the bot

---

### 4. Job/Background Task Layer

**Strategy:** Log and continue (don't crash scheduler)

```python
# jobs/order_timeout_job.py
async def check_expired_orders():
    """Check for expired orders. Logs errors but continues."""
    try:
        await OrderService.expire_pending_orders()
    except ShopBotException as e:
        logging.error(f"Error expiring orders: {e}")
        # Don't re-raise - job scheduler should continue
    except Exception as e:
        logging.exception(f"Unexpected error in order timeout job: {e}")
        # Don't re-raise - job scheduler should continue
```

**Rationale:**
- Background jobs should be resilient
- One failed job shouldn't stop all jobs
- Log for debugging

**Rules:**
-  Catch all exceptions
-  Log with context
-  Continue execution (don't re-raise)
-  Send admin alerts for critical failures

---

## Exception Usage Examples

### OrderNotFoundException

```python
# Raise in service:
order = await OrderRepository.get_by_id(order_id, session)
if not order:
    raise OrderNotFoundException(order_id)

# Catch in handler:
except OrderNotFoundException:
    await callback.answer(" Order not found", show_alert=True)
```

### InsufficientStockException

```python
# Raise in service:
if item.available_qty < requested_qty:
    raise InsufficientStockException(
        item_id=item.id,
        requested=requested_qty,
        available=item.available_qty
    )

# Catch in handler:
except InsufficientStockException as e:
    await callback.answer(
        f" Insufficient stock: {e.available} available, {e.requested} requested",
        show_alert=True
    )
```

### CryptocurrencyNotSelectedException

```python
# Raise in service:
if crypto_currency == Cryptocurrency.PENDING_SELECTION:
    raise CryptocurrencyNotSelectedException(order_id)

# Catch in handler:
except CryptocurrencyNotSelectedException:
    await callback.answer(
        " Please select a cryptocurrency first",
        show_alert=True
    )
```

---

## Migration from Old Pattern

### Before (Inconsistent)

```python
# Pattern A: Return None
def get_order(order_id):
    try:
        order = repository.get(order_id)
        return order
    except Exception as e:
        logging.error(f"Error: {e}")
        return None  #  Ambiguous - not found or error?

# Pattern B: Generic ValueError
def get_order(order_id):
    order = repository.get(order_id)
    if not order:
        raise ValueError(f"Order {order_id} not found")  #  Not specific

# Pattern C: Swallow exception
def get_order(order_id):
    try:
        order = repository.get(order_id)
        return order
    except Exception as e:
        logging.error(f"Error: {e}")
        pass  #  Hides errors
```

### After (Consistent)

```python
from exceptions.order import OrderNotFoundException

def get_order(order_id: int, session) -> Order:
    """
    Get order by ID.

    Args:
        order_id: Order ID
        session: Database session

    Returns:
        Order instance

    Raises:
        OrderNotFoundException: If order not found
    """
    order = await OrderRepository.get_by_id(order_id, session)
    if not order:
        raise OrderNotFoundException(order_id)  #  Specific, type-safe
    return order
```

---

## Benefits

### 1. Type Safety
```python
# Type checker knows exact exception type
except OrderNotFoundException as e:
    print(e.order_id)  #  IDE autocomplete works
```

### 2. Clear API Contracts
```python
# Docstring declares possible exceptions
"""
Raises:
    OrderNotFoundException: If order not found
    InsufficientStockException: If stock insufficient
"""
```

### 3. Centralized Error Messages
```python
# Exception contains context
OrderNotFoundException(order_id=123)
# Message: "Order 123 not found"
# Details: {'order_id': 123}
```

### 4. Easier Testing
```python
# Test specific exception
with pytest.raises(OrderNotFoundException) as exc_info:
    await OrderService.get_order(999, session)
assert exc_info.value.order_id == 999
```

---

## Anti-Patterns to Avoid

###  Generic Exception
```python
raise Exception("Something went wrong")  # Not specific enough
```

###  String-Based Errors
```python
return {"error": "Order not found"}  # Not type-safe
```

###  Silent Failures
```python
except Exception:
    pass  # Hides errors
```

###  Catching Too Broadly
```python
try:
    # 50 lines of code
except Exception:
    # Which line failed? Unknown!
```

###  Logging Without Context
```python
logging.error("Error occurred")  # No context
```

---

## Implementation Checklist

Services:
- [x] services/payment.py - OrderNotFoundException, CryptocurrencyNotSelectedException
- [x] services/shipping.py - OrderNotFoundException
- [x] services/buy.py - OrderNotFoundException
- [ ] services/order.py - Various order exceptions
- [ ] services/cart.py - Cart exceptions
- [ ] services/item.py - Item exceptions
- [ ] services/user.py - User exceptions

Handlers:
- [ ] handlers/user/order.py - Catch OrderNotFoundException
- [ ] handlers/user/cart.py - Catch CartException
- [ ] handlers/admin/shipping_management.py - Catch ShippingException

---

## Next Steps

1. **Complete Service Layer Migration** (services/order.py, cart.py, etc.)
2. **Update Handlers** to catch custom exceptions
3. **Add Localized Error Messages** (l10n/en.json, de.json)
4. **Write Tests** for exception scenarios
5. **Update API Documentation** with exception contracts

---

## Related Documentation

- `exceptions/__init__.py` - Exception hierarchy
- `TODO/2025-11-01_TODO_software-engineering-audit.md` - Issue 5

---

**Status:** Phase 1 Complete (Exception classes created, services partially migrated)
**Next:** Complete service layer migration and update handlers
