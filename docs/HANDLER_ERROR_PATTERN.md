# Handler Error Handling Pattern

**Date:** 2025-11-03
**Related:** docs/ERROR_HANDLING_STRATEGY.md

---

## Standard Pattern for Handlers

All handlers should follow this error handling pattern:

```python
from aiogram.types import CallbackQuery
from exceptions import (
    ShopBotException,
    OrderNotFoundException,
    InvalidOrderStateException,
    CryptocurrencyNotSelectedException
)

@router.callback_query(SomeCallback.filter(F.action == "some_action"))
async def some_handler(callback: CallbackQuery, **kwargs):
    """Handler with proper error handling."""
    try:
        session = kwargs['session']

        # Call service layer
        result = await SomeService.do_something(some_id, session)

        # Build and send response
        msg = " Success!"
        await callback.message.edit_text(msg)

    except OrderNotFoundException:
        # Specific exception - user-friendly message
        await callback.answer(
            " Order not found",
            show_alert=True
        )

    except InvalidOrderStateException as e:
        # Specific exception with context
        await callback.answer(
            f" Cannot perform action: Order is {e.current_state}",
            show_alert=True
        )

    except CryptocurrencyNotSelectedException:
        # Specific exception
        await callback.answer(
            " Please select a cryptocurrency first",
            show_alert=True
        )

    except ShopBotException as e:
        # Catch-all for bot exceptions
        await callback.answer(
            f" Error: {str(e)}",
            show_alert=True
        )

    except Exception as e:
        # Unexpected errors - log and show generic message
        logging.exception(f"Unexpected error in some_handler: {e}")
        await callback.answer(
            " An unexpected error occurred. Please try again later.",
            show_alert=True
        )
```

---

## Key Principles

### 1. Order Matters
Catch **specific exceptions first**, then broader ones:

 Correct order:
```python
except OrderNotFoundException:  # Most specific
except InvalidOrderStateException:
except ShopBotException:  # Broader
except Exception:  # Broadest
```

 Wrong order:
```python
except ShopBotException:  # Catches everything!
except OrderNotFoundException:  # Never reached
```

---

### 2. User-Friendly Messages

Always show user-friendly messages:

 Good:
```python
except OrderNotFoundException:
    await callback.answer(" Order not found", show_alert=True)
```

 Bad:
```python
except OrderNotFoundException as e:
    await callback.answer(str(e), show_alert=True)
    # Shows: "Order 123 not found" - too technical
```

---

### 3. Use show_alert=True for Errors

Errors should use `show_alert=True` to ensure visibility:

```python
await callback.answer(" Error message", show_alert=True)
```

---

### 4. Log Unexpected Errors

Always log unexpected errors for debugging:

```python
except Exception as e:
    logging.exception(f"Unexpected error in handler: {e}")
    await callback.answer(" An error occurred", show_alert=True)
```

---

## Common Exception Handlers

### OrderNotFoundException

```python
except OrderNotFoundException:
    await callback.answer(
        " Order not found",
        show_alert=True
    )
```

### InvalidOrderStateException

```python
except InvalidOrderStateException as e:
    await callback.answer(
        f" Cannot cancel order: Order is {e.current_state}",
        show_alert=True
    )
```

### CryptocurrencyNotSelectedException

```python
except CryptocurrencyNotSelectedException:
    await callback.answer(
        " Please select a cryptocurrency first",
        show_alert=True
    )
```

### ItemNotFoundException

```python
except ItemNotFoundException:
    await callback.answer(
        " Item not available",
        show_alert=True
    )
```

### InsufficientStockException

```python
except InsufficientStockException as e:
    await callback.answer(
        f" Insufficient stock: {e.available} available, {e.requested} requested",
        show_alert=True
    )
```

### UserBannedException

```python
except UserBannedException as e:
    await callback.answer(
        f" You are banned: {e.reason}",
        show_alert=True
    )
```

### InsufficientBalanceException

```python
except InsufficientBalanceException as e:
    await callback.answer(
        f" Insufficient balance: €{e.required:.2f} required, €{e.available:.2f} available",
        show_alert=True
    )
```

---

## Anti-Patterns to Avoid

###  Don't Catch Too Broadly

```python
# BAD: Hides specific errors
try:
    await OrderService.cancel_order(order_id, session)
except Exception:
    await callback.answer("Error", show_alert=True)
```

###  Don't Swallow Exceptions

```python
# BAD: Silently fails
try:
    await OrderService.cancel_order(order_id, session)
except OrderNotFoundException:
    pass  # User sees nothing!
```

###  Don't Show Technical Details

```python
# BAD: Exposes internal details
except OrderNotFoundException as e:
    await callback.answer(f"Database error: {repr(e)}", show_alert=True)
```

###  Don't Re-raise in Handlers

```python
# BAD: Crashes bot
try:
    await OrderService.cancel_order(order_id, session)
except OrderNotFoundException as e:
    logging.error(f"Error: {e}")
    raise  # Don't do this in handlers!
```

---

## Localized Error Messages (Future)

For internationalization, use localization:

```python
except OrderNotFoundException:
    msg = Localizator.get_text(BotEntity.USER, "error_order_not_found")
    await callback.answer(msg, show_alert=True)
```

**l10n/en.json:**
```json
{
  "user": {
    "error_order_not_found": " Order not found",
    "error_order_cannot_cancel": " Cannot cancel order: Order is {status}",
    "error_crypto_not_selected": " Please select a cryptocurrency first"
  }
}
```

---

## Migration Checklist

When migrating handlers:

- [ ] Identify service calls that can throw exceptions
- [ ] Add try-except blocks
- [ ] Catch specific exceptions first
- [ ] Show user-friendly messages with show_alert=True
- [ ] Log unexpected errors
- [ ] Test error scenarios

---

**Status:** Pattern Documented
**Next Step:** Apply pattern to all handlers calling services
