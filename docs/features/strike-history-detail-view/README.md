# Strike History Detail View

## Feature Overview

Extends the admin user management with a detailed view for banned users, displaying the complete strike history with timestamps, strike types, order IDs, and reasons.

## Architecture

### Service/Handler Separation

The feature implementation strictly follows the Layered Architecture pattern:

**Service Layer** (`services/admin.py`):
- `get_banned_user_detail_data(user_id: int, session) -> dict | None`
- Returns pure data (dict), no Telegram objects
- Business Logic: Load user, fetch strikes, sort, format
- Testable without Telegram dependencies

**Handler Layer** (`handlers/admin/user_management.py`):
- `banned_user_detail(**kwargs)`
- Builds Telegram-specific objects (`InlineKeyboardBuilder`, message text)
- Calls service, formats data for Telegram
- Manages UI logic (buttons, localization)

### Navigation Flow

```
Level 0: Admin Menu
Level 1: User Management → Credit Management
Level 2: Banned Users List
Level 3: Strike History Detail View (NEW!) ← Operation-based routing
Level 4: Unban Confirmation
```

**Level 3 Router**:
- `operation=UNBAN_USER` → `banned_user_detail()` (new detail view)
- `operation=REFUND` → `refund_confirmation()` (existing refund logic)

Prevents breaking changes to existing refund functionality.

## Data Structure

Service layer returns dict:

```python
{
    "user_id": int,
    "telegram_id": int,
    "telegram_username": str | None,
    "strike_count": int,
    "blocked_at": datetime | None,
    "blocked_reason": str | None,
    "strikes": [
        {
            "created_at": datetime,
            "strike_type": str,  # "TIMEOUT" | "LATE_CANCEL"
            "order_invoice_id": str | None,  # "INV-XXXX-ABCDEF" or None
            "reason": str | None
        }
    ],
    "total_strike_count": int  # For truncation message
}
```

## Implementation Details

### Strikes Limit

- **Max 10 Strikes** displayed (message length protection)
- `total_strike_count` for truncation message when >10
- Sorting: Newest first (reverse chronological)

### Invoice ID Resolution

- Strike → Order → Invoice (first invoice = main invoice)
- Fallback to `None` when order/invoice missing
- Uses `invoice_number` field (not legacy `invoice_id`)

### HTML Escaping

- All user inputs are escaped: `safe_html()`
- Applies to: `telegram_username`, `strike.reason`, `user.blocked_reason`

## Localization

13 new keys (DE + EN):

| Key | DE | EN |
|-----|----|----|
| `banned_user_detail_header` | Gesperrter Benutzer | Banned User |
| `strike_history_header` | Strike-Historie | Strike History |
| `strike_type_timeout` | Timeout | Timeout |
| `strike_type_late_cancel` | Verspätete Stornierung | Late Cancellation |
| `no_order_id` | Keine Order | No Order |
| `no_reason_given` | Kein Grund angegeben | No reason given |
| `strike_history_item` | Strike {N}: {date}... | Strike {N}: {date}... |
| `strike_history_truncated` | ... und X weitere | ... and X more |
| `no_strikes_found` | Keine Strikes gefunden | No strikes found |
| `ban_info_header` | Sperrinfo | Ban Information |
| `unknown_date` | Unbekannt | Unknown |
| `ban_info_details` | Gesperrt am... | Banned on... |
| `unban_user_button_detail` | Entsperren | Unban |

## Testing

### Unit Tests

`tests/admin/unit/test_banned_user_detail.py`: 12 tests

**Test Coverage**:
1. Service returns dict (no Telegram objects)
2. Returns None for non-existent users
3. Returns None for non-banned users
4. Correct user data returned
5. Strikes sorted (newest first)
6. Strike data structure validation
7. Invoice ID when order exists
8. None invoice ID without order
9. Limitation to 10 strikes
10. total_strike_count for truncation
11. User without strikes
12. User without username

**Test Results**: ✅ 12/12 passed

### Manual Testing

See `MANUAL_TEST_PLAN.md` in this directory.

## Files Changed

### New Files
- `tests/admin/unit/test_banned_user_detail.py`
- `docs/features/strike-history-detail-view/README.md`
- `docs/features/strike-history-detail-view/MANUAL_TEST_PLAN.md`

### Modified Files
- `services/admin.py`: Added `get_banned_user_detail_data()`
- `handlers/admin/user_management.py`: Added `level_3_router()`, `banned_user_detail()`
- `l10n/de.json`: 13 new keys
- `l10n/en.json`: 13 new keys

## Lessons Learned

### Service/Handler Separation

**Problem**: Original implementation had `CallbackQuery` and `InlineKeyboardBuilder` in service layer.

**Solution**: Service returns only data (dict), handler builds Telegram objects.

**Benefits**:
- Service is testable without Telegram mocks
- Service can be reused from other contexts
- Clear separation: Service = Business Logic, Handler = UI Logic

### Order/Invoice Relationship

**Problem**: Order has no `invoice_id` column, but `invoices` relationship (1:N for partial payments).

**Solution**: `strike.order.invoices[0].invoice_number` for main invoice.

**Learning**: Always check actual DB structure, don't assume!

## Related Features

- Strike System: `services/strike.py`, `models/user_strike.py`
- User Management: `handlers/admin/user_management.py`
- Unban Functionality: `services/admin.py::unban_user()`