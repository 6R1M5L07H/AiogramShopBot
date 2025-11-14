# Strike History with Timestamps in Admin Unban User Detail View

**Priority:** Medium
**Status:** TODO
**Estimated Effort:** Small (1-2 hours)

## Description

Add a detail view between the banned users list and the unban action that shows the complete strike history for each banned user, including:
- Exact timestamp (date + time) for each strike
- Strike type (TIMEOUT, LATE_CANCELLATION, etc.)
- Related order ID (if applicable)
- Strike reason text

This provides admins with full transparency on why and when a user accumulated strikes, enabling better-informed unban decisions.

## Current State

Currently in `handlers/admin/user_management.py` and `services/admin.py`:
- **Level 2** (`get_banned_users_list`): Shows list of all banned users with basic info (username, strike count, ban date, ban reason) and direct unban button
- **Level 4** (`unban_user`): Executes unban immediately
- **Missing:** Detail view showing individual strike history

## What Already Exists

✅ **UserStrike Model** (`models/user_strike.py`):
```python
class UserStrike(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    strike_type = Column(SQLEnum(StrikeType), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    reason = Column(String, nullable=True)
```

✅ **UserStrikeRepository** (`repositories/user_strike.py`):
- `get_by_user_id(user_id, session)` - Already fetches all strikes for a user

✅ **StrikeType Enum** (`enums/strike_type.py`):
- Defines strike types (TIMEOUT, LATE_CANCELLATION, etc.)

## Requirements

### New Level 3: Banned User Detail View

**Display Format:**
```
👤 Banned User Details

Username: @banned_user
Telegram ID: 123456789
Strikes: 3 / 3

━━━━━━━━━━━━━━━━━━━━━━
⚠️ Strike History:

1️⃣ 15.10.2024 14:23
   Type: Late Order Cancellation
   Order: #12345
   Reason: Order cancelled after grace period

2️⃣ 22.10.2024 09:15
   Type: Payment Timeout
   Order: #12389
   Reason: Payment not received within timeout

3️⃣ 01.11.2024 18:42
   Type: Payment Timeout
   Order: #12456
   Reason: Payment not received within timeout
━━━━━━━━━━━━━━━━━━━━━━

🚫 Ban Status:
Banned: 01.11.2024 18:45
Reason: Automatic ban: 3 strikes (threshold: 3)

[✅ Unban User] [⬅️ Back to List]
```

**Information to Display:**
- Username / Telegram ID
- Total strikes (e.g., "3 / 3")
- **Strike History** (newest first):
  - Numbered list (1️⃣, 2️⃣, 3️⃣)
  - Timestamp: `DD.MM.YYYY HH:MM`
  - Strike Type: Localized (e.g., "Late Order Cancellation", "Payment Timeout")
  - Order ID: `#12345` (if applicable)
  - Reason: Text from `UserStrike.reason` field
- Ban date and reason

**Actions:**
- ✅ **Unban User** (navigate to Level 4)
- ⬅️ **Back to List** (navigate to Level 2)

## Implementation Plan

### Phase 1: Service Layer

**Add to `services/admin.py`:**

```python
@staticmethod
async def get_banned_user_detail(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
    """
    Display detailed view of a single banned user with full strike history.

    Shows:
    - Username/ID
    - Total strike count
    - Individual strikes with timestamps, types, order IDs, reasons
    - Ban date and reason
    - Unban button
    """
    from repositories.user import UserRepository
    from repositories.user_strike import UserStrikeRepository
    from enums.strike_type import StrikeType

    unpacked_cb = UserManagementCallback.unpack(callback.data)
    user_id = unpacked_cb.page  # user_id stored in page field

    # Get user
    user = await UserRepository.get_by_id(user_id, session)

    if not user:
        return Localizator.get_text(BotEntity.ADMIN, "user_not_found"), InlineKeyboardBuilder()

    # Get all strikes for this user
    strikes = await UserStrikeRepository.get_by_user_id(user_id, session)
    strikes_sorted = sorted(strikes, key=lambda s: s.created_at, reverse=True)  # Newest first

    # Format username
    if user.telegram_username:
        user_display = f"@{safe_html(user.telegram_username)}"
    else:
        user_display = f"ID: {user.telegram_id}"

    # Build message
    message = Localizator.get_text(BotEntity.ADMIN, "banned_user_detail_header").format(
        user_display=user_display,
        telegram_id=user.telegram_id,
        strike_count=len(strikes),
        max_strikes=config.MAX_STRIKES_BEFORE_BAN
    )

    # Add strike history
    if strikes_sorted:
        message += "\n" + Localizator.get_text(BotEntity.ADMIN, "strike_history_separator")
        message += "\n" + Localizator.get_text(BotEntity.ADMIN, "strike_history_header")

        for idx, strike in enumerate(strikes_sorted, start=1):
            timestamp = strike.created_at.strftime("%d.%m.%Y %H:%M")
            strike_type_localized = Localizator.get_text(BotEntity.ADMIN, f"strike_type_{strike.strike_type.value}")

            strike_entry = Localizator.get_text(BotEntity.ADMIN, "strike_entry").format(
                number=idx,
                emoji=get_number_emoji(idx),
                timestamp=timestamp,
                strike_type=strike_type_localized,
                order_id=f"#{strike.order_id}" if strike.order_id else "N/A",
                reason=safe_html(strike.reason) if strike.reason else "N/A"
            )
            message += strike_entry

        message += "\n" + Localizator.get_text(BotEntity.ADMIN, "strike_history_separator")
    else:
        message += "\n" + Localizator.get_text(BotEntity.ADMIN, "no_strikes_found")

    # Add ban info
    ban_date = user.blocked_at.strftime("%d.%m.%Y %H:%M") if user.blocked_at else "Unknown"
    message += "\n\n" + Localizator.get_text(BotEntity.ADMIN, "ban_info").format(
        ban_date=ban_date,
        ban_reason=safe_html(user.blocked_reason) if user.blocked_reason else "Unknown"
    )

    # Build keyboard
    kb_builder = InlineKeyboardBuilder()

    # Unban button
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "unban_user_button_detail"),
        callback_data=UserManagementCallback.create(
            level=4,  # Unban action
            operation=UserManagementOperation.UNBAN_USER,
            page=user_id
        )
    )

    # Back button
    kb_builder.row(
        unpacked_cb.get_back_button(level=2)  # Back to banned users list
    )

    return message, kb_builder
```

**Helper function for number emojis:**
```python
def get_number_emoji(num: int) -> str:
    """Return number emoji for strike list (1️⃣, 2️⃣, etc.)"""
    emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"}
    return emojis.get(num, f"{num}.")
```

### Phase 2: Update Existing List View

**Modify `get_banned_users_list` in `services/admin.py` (Line 248-281):**

Change the button behavior from direct unban to detail view:
```python
# OLD (Line 273-280):
kb_builder.button(
    text=Localizator.get_text(BotEntity.ADMIN, "unban_user_button").format(user_display=user_display),
    callback_data=UserManagementCallback.create(
        level=4,  # Direct unban
        operation=UserManagementOperation.UNBAN_USER,
        page=user.id
    )
)

# NEW:
kb_builder.button(
    text=Localizator.get_text(BotEntity.ADMIN, "view_user_details_button").format(user_display=user_display),
    callback_data=UserManagementCallback.create(
        level=3,  # NEW: Detail view
        operation=UserManagementOperation.UNBAN_USER,
        page=user.id
    )
)
```

### Phase 3: Update Handler

**Modify `handlers/admin/user_management.py` (Line 88-94):**

Add new level 3 handler:
```python
levels = {
    0: user_management_menu,
    1: credit_management,
    2: refund_buy,
    3: refund_confirmation,
    4: unban_user_handler
}

# Change to:
levels = {
    0: user_management_menu,
    1: credit_management,
    2: refund_buy,
    3: banned_user_detail,  # NEW: Detail view
    4: refund_confirmation,
    5: unban_user_handler   # Moved from 4 to 5
}
```

**Add new handler function:**
```python
async def banned_user_detail(**kwargs):
    """Show detailed view of banned user with strike history."""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await AdminService.get_banned_user_detail(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
```

**WAIT - Conflict with refund flow!** Level 3 and 4 are already used by refund. Need to check callback routing logic.

### Phase 3 (Revised): Callback Routing Strategy

**Option A: Use `operation` field to distinguish flows**
- Level 3 with `operation=UNBAN_USER` → Banned user detail
- Level 3 with `operation=REFUND` → Refund confirmation (existing)

**Option B: Use separate level numbers**
- Refund flow: Levels 2, 3, 4 (as is)
- Unban flow: Levels 2 (list), 5 (detail), 6 (execute)

**Decision: Use Option A** (cleaner, leverages existing operation field)

**Update handler routing:**
```python
async def level_3_router(**kwargs):
    """Route Level 3 based on operation type."""
    callback = kwargs.get("callback")
    unpacked_cb = UserManagementCallback.unpack(callback.data)

    if unpacked_cb.operation == UserManagementOperation.UNBAN_USER:
        return await banned_user_detail(**kwargs)
    else:
        return await refund_confirmation(**kwargs)

levels = {
    0: user_management_menu,
    1: credit_management,
    2: refund_buy,
    3: level_3_router,  # Routes based on operation
    4: unban_user_handler
}
```

### Phase 4: Localization

**Add to `l10n/de.json` and `l10n/en.json`:**

```json
{
  "banned_user_detail_header": "👤 Details zum gesperrten Benutzer\n\nUsername: {user_display}\nTelegram ID: {telegram_id}\nStrikes: {strike_count} / {max_strikes}\n",
  "strike_history_separator": "━━━━━━━━━━━━━━━━━━━━━━",
  "strike_history_header": "⚠️ Strike-Verlauf:\n",
  "strike_entry": "\n{emoji} {timestamp}\n   Typ: {strike_type}\n   Order: {order_id}\n   Grund: {reason}\n",
  "no_strikes_found": "\nKeine Strikes gefunden (Fehler im System)",
  "ban_info": "🚫 Gesperrt am: {ban_date}\nGrund: {ban_reason}",
  "view_user_details_button": "🔍 Details: {user_display}",
  "unban_user_button_detail": "✅ Benutzer entsperren",
  "strike_type_TIMEOUT": "Zahlungs-Timeout",
  "strike_type_LATE_CANCELLATION": "Verspätete Stornierung"
}
```

**English (`l10n/en.json`):**
```json
{
  "banned_user_detail_header": "👤 Banned User Details\n\nUsername: {user_display}\nTelegram ID: {telegram_id}\nStrikes: {strike_count} / {max_strikes}\n",
  "strike_history_separator": "━━━━━━━━━━━━━━━━━━━━━━",
  "strike_history_header": "⚠️ Strike History:\n",
  "strike_entry": "\n{emoji} {timestamp}\n   Type: {strike_type}\n   Order: {order_id}\n   Reason: {reason}\n",
  "no_strikes_found": "\nNo strikes found (system error)",
  "ban_info": "🚫 Banned: {ban_date}\nReason: {ban_reason}",
  "view_user_details_button": "🔍 Details: {user_display}",
  "unban_user_button_detail": "✅ Unban User",
  "strike_type_TIMEOUT": "Payment Timeout",
  "strike_type_LATE_CANCELLATION": "Late Cancellation"
}
```

### Phase 5: StrikeType Enum Check

**Verify all strike types in `enums/strike_type.py`:**
```python
class StrikeType(str, Enum):
    TIMEOUT = "TIMEOUT"
    LATE_CANCELLATION = "LATE_CANCELLATION"
    # ... add localization keys for any other types
```

Add corresponding `strike_type_{value}` keys to localization files.

### Phase 6: Testing

**Test Scenarios:**
- [ ] User with 0 strikes (edge case - should not be banned, but test data safety)
- [ ] User with 1 strike (single entry display)
- [ ] User with 3 strikes (multiple entries, max strikes)
- [ ] Strike with order_id present
- [ ] Strike with order_id = None
- [ ] Strike with reason text
- [ ] Strike with reason = None
- [ ] Strikes in correct order (newest first)
- [ ] Timestamp format correct (DD.MM.YYYY HH:MM)
- [ ] Strike types localized correctly (German/English)
- [ ] Message length within Telegram limit (4096 chars)
- [ ] Navigation: List → Detail → Back to List (preserves state)
- [ ] Navigation: Detail → Unban → Success message
- [ ] Unban functionality still works after adding detail view

## Technical Notes

### Message Length Considerations

Telegram message limit: **4096 characters**

**Mitigation if message too long:**
- Limit strike history to last 10 strikes
- Use truncated format for older strikes
- Add note: "Showing last 10 strikes" if more exist

**Implementation:**
```python
MAX_STRIKES_DISPLAY = 10
strikes_to_display = strikes_sorted[:MAX_STRIKES_DISPLAY]

if len(strikes_sorted) > MAX_STRIKES_DISPLAY:
    message += f"\n(Showing {MAX_STRIKES_DISPLAY} of {len(strikes_sorted)} strikes)"
```

### StrikeType Localization Pattern

**Pattern:**
- Enum value: `StrikeType.TIMEOUT`
- Localization key: `strike_type_TIMEOUT`
- Displayed text: "Zahlungs-Timeout" (DE) / "Payment Timeout" (EN)

**Fallback for unknown types:**
```python
strike_type_key = f"strike_type_{strike.strike_type.value}"
strike_type_localized = Localizator.get_text(BotEntity.ADMIN, strike_type_key, default=strike.strike_type.value)
```

### Navigation Flow

**Before:**
```
Level 0 (Menu) → Level 1 (Credit Mgmt) → Level 2 (Banned Users List) → Level 4 (Unban Execute)
```

**After:**
```
Level 0 (Menu) → Level 1 (Credit Mgmt) → Level 2 (Banned Users List) → Level 3 (Detail View) → Level 4 (Unban Execute)
```

**Refund flow (unchanged):**
```
Level 0 (Menu) → Level 1 (Credit Mgmt) → Level 2 (Refund Menu) → Level 3 (Refund Confirm) → Done
```

**Conflict Resolution:** Use `operation` field in Level 3 router to distinguish flows.

## Benefits

- Full transparency on user ban history for admins
- Better-informed unban decisions (see pattern of behavior)
- Ability to distinguish one-time mistakes from repeat offenders
- Improved admin confidence in strike system
- No database changes required (all data already exists)

## Estimated Timeline

- Phase 1 (Service Layer): 30min
- Phase 2 (Update List View): 15min
- Phase 3 (Handler Routing): 20min
- Phase 4 (Localization): 15min
- Phase 5 (StrikeType Check): 5min
- Phase 6 (Testing): 30min

**Total: 1-2 hours**

## Dependencies

- Existing: `UserStrike` model
- Existing: `UserStrikeRepository`
- Existing: `StrikeType` enum
- Existing: `get_banned_users_list()` in AdminService
- Existing: `unban_user()` in AdminService

## Future Enhancements (Optional)

- [ ] Admin ability to remove individual strikes
- [ ] Strike decay system (strikes expire after X days)
- [ ] Export strike history to CSV
- [ ] Pagination for strike history if >10 strikes
- [ ] Link to order detail view from strike entry
