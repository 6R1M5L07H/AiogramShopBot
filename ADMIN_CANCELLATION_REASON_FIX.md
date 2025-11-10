# Admin Cancellation Custom Reason Fix

## Problem

When admin cancels an order with a custom reason, the reason is not displayed to the user in the notification message.

**Current Flow:**
1. Admin enters custom reason in FSM → ✅ Stored in FSM context
2. Reason passed to `OrderService.cancel_order()` → ✅ Correct
3. Reason passed to `NotificationService.build_order_cancelled_by_admin_message()` → ✅ Correct
4. Reason passed to `InvoiceFormatterService.format_complete_order_view()` → ✅ Correct
5. **BUT**: Formatter does NOT display `cancellation_reason` for `admin_cancellation` header type → ❌ **BUG**

**Bug Location:** `services/invoice_formatter.py:791-793`

```python
if header_type == "admin_cancellation":
    message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"
    message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"
```

The code ignores the `cancellation_reason` parameter!

## Solution

Add `cancellation_reason` display after the admin cancel notice:

```python
if header_type == "admin_cancellation":
    message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"

    # Display custom reason if provided
    if cancellation_reason:
        message += f"<b>{Localizator.get_text(entity, 'admin_cancel_reason_label')}</b>\n"
        message += f"{cancellation_reason}\n\n"

    message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"
```

## Implementation

File: `services/invoice_formatter.py`
Lines: 791-793

### Before (Bug):
```python
if header_type == "admin_cancellation":
    message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"
    message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"
```

### After (Fixed):
```python
if header_type == "admin_cancellation":
    message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"

    # Display custom reason if provided
    if cancellation_reason:
        message += f"<b>{Localizator.get_text(entity, 'admin_cancel_reason_label')}</b>\n"
        message += f"{cancellation_reason}\n\n"

    message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"
```

## Localization Keys Required

Already exist in `l10n/de.json` and `l10n/en.json`:
- `admin_cancel_reason_label`: "Grund für die Stornierung:" (de) / "Cancellation reason:" (en)

## Testing

1. Admin cancels order with custom reason: "Artikel nicht mehr verfügbar"
2. User receives notification with complete invoice
3. **After fix**: Message includes section:
   ```
   Grund für die Stornierung:
   Artikel nicht mehr verfügbar
   ```
4. **Before fix**: Reason was missing entirely

## Security Note

The `cancellation_reason` is already HTML-escaped in `NotificationService.build_order_cancelled_by_admin_message()` (line 567):
```python
escaped_reason = safe_html(custom_reason)
```

So no XSS vulnerability - the escaping happens **before** passing to formatter.
