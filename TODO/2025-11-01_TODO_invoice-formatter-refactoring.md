# Invoice Formatter Refactoring

**Branch:** `feature/invoice-formatter-refactoring`
**Status:** TODO (nach Merge von feature/admin-cancellation-custom-reason)
**Priority:** Medium

## Problem

Aktuell existiert die gleiche Order/Invoice-Formatierungs-Logik 4-5x dupliziert:
1. Admin View (shipping_management.py: show_order_details)
2. User Payment Screen (order.py: _format_payment_screen)
3. User Wallet Payment Invoice (order.py: _format_wallet_payment_invoice)
4. Notification - Wallet Refund (notification.py: build_order_cancelled_wallet_refund_message)
5. Notification - Admin Cancel (notification.py: build_order_cancelled_by_admin_message)

## Ziel

Zentrale `InvoiceFormatter` Service-Klasse mit konfigurierbaren Optionen.

## Implementation Plan

### 1. Create InvoiceFormatter Service
- [ ] Create `services/invoice_formatter.py`
- [ ] Define `InvoiceFormatter` class with static method `format_order_invoice()`
- [ ] Options dict for customization:
  - `show_digital_section`: Separate section for digital items
  - `show_physical_section`: Separate section for physical items
  - `show_refund_line`: Refund line in totals
  - `show_wallet_line`: Wallet usage line
  - `show_payment_info`: Crypto payment details
  - `title`: Invoice header title
  - `status_text`: Status text (e.g., "CANCELLED")
  - `custom_sections`: Additional custom sections

### 2. Refactor Admin View
- [ ] Update `handlers/admin/shipping_management.py`
- [ ] Replace `show_order_details()` formatting with `InvoiceFormatter.format_order_invoice()`
- [ ] Test admin shipping management view

### 3. Refactor Payment Screens
- [ ] Update `services/order.py`
- [ ] Replace `_format_payment_screen()` with InvoiceFormatter
- [ ] Replace `_format_wallet_payment_invoice()` with InvoiceFormatter
- [ ] Test payment flow (crypto + wallet-only)

### 4. Refactor Notifications
- [ ] Update `services/notification.py`
- [ ] Replace formatting in `build_order_cancelled_wallet_refund_message()`
- [ ] Replace formatting in `build_order_cancelled_by_admin_message()`
- [ ] Test cancellation notifications

### 5. Testing
- [ ] Test all views still display correctly
- [ ] Test admin order management
- [ ] Test user payment screens
- [ ] Test cancellation notifications (user + admin)
- [ ] Visual regression testing

## Benefits

- ✅ Single source of truth for invoice formatting
- ✅ Consistent display across all contexts
- ✅ Easy to update formatting globally
- ✅ Reduced code duplication (~200+ lines saved)
- ✅ Better maintainability

## Notes

- Keep backwards compatibility during refactoring
- Ensure all localization strings still work
- Test with both digital and physical items
- Test with mixed orders
