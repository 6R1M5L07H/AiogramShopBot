# User Management with User List and Detail View

**Priority:** Medium
**Status:** TODO
**Estimated Effort:** Medium (4-6 hours)

## Description

Extend existing Admin User Management with:
- User list overview with pagination (all users)
- Individual user detail view showing:
  - Total amount spent
  - Ban/Unban action
  - Strike count
  - Registration date
  - Direct Telegram contact link
- Search/filter capabilities (optional)

## Current State

Currently `handlers/admin/user_management.py`:
- Menu with operations: Credit Management, Refund, Unban User
- Credit management requires manual user ID/username input (FSM-based)
- Banned users list shows only banned users
- No overview of all users
- No detailed user profile view
- No "Total Amount Spent" tracking

## Requirements

### 1. User List Overview (New Level 5)
- Show all registered users with pagination
- Format per user: `Username (@username or ID) - Registered: DD.MM.YYYY`
- Pagination: 10 users per page
- Each user clickable → navigate to user detail view (Level 6)
- Search bar (optional Phase 2): Filter by username/ID

### 2. User Detail View (New Level 6)

**Display:**
- **User Information:**
  - Username: @username (or "No username")
  - Telegram ID: 123456789
  - Registration Date: DD.MM.YYYY HH:MM

- **Statistics:**
  - Total Amount Spent: XXX.XX EUR
  - Wallet Balance: XXX.XX EUR
  - Successful Orders Count: X
  - Strike Count: X / MAX (e.g. "2 / 3")

- **Status:**
  - Ban Status: Banned / Active
  - Ban Date: DD.MM.YYYY HH:MM (if banned)
  - Ban Reason: "..." (if banned)

- **Referral Info (if applicable):**
  - Referral Code: XXXXXXXX (if eligible)
  - Successful Referrals: X / MAX

**Actions:**
- 📨 **Contact User** (tg://user?id={telegram_id} deep link)
- 🚫 **Ban User** (if not banned) / ✅ **Unban User** (if banned)
- 💰 **Adjust Wallet Balance** (existing credit management)
- 📋 **View Order History** (link to Order Management filtered by user)
- ⬅️ **Back to User List**

### 3. Total Amount Spent Calculation

Calculate from:
- All orders with status `PAID`, `SHIPPED`, `PAID_AWAITING_SHIPMENT`
- Sum of `Order.total_price` for completed orders
- Store as computed value or calculate on-demand

## Implementation Plan

### Phase 1: Repository Layer

**Add to UserRepository:**
- [ ] `get_all_users_paginated()`:
  - Parameters: `limit: int = 10`, `offset: int = 0`, `session: AsyncSession | Session`
  - Return users ordered by `registered_at DESC` (newest first)
  - Include only active fields (not deleted/soft-deleted if applicable)

- [ ] `count_all_users()`:
  - Return total user count for pagination

- [ ] `get_user_statistics()`:
  - Parameters: `user_id: int`, `session: AsyncSession | Session`
  - Return structured data:
    ```python
    {
        "total_amount_spent": Decimal,  # From Order.total_price (PAID/SHIPPED/PAID_AWAITING_SHIPMENT)
        "wallet_balance": Decimal,       # User.top_up_amount
        "successful_orders_count": int,  # User.successful_orders_count
        "strike_count": int,             # User.strike_count
        "max_strikes": int,              # From config
        "is_banned": bool,               # User.is_blocked
        "ban_date": Optional[datetime],  # User.blocked_at
        "ban_reason": Optional[str],     # User.blocked_reason
        "referral_code": Optional[str],  # User.referral_code (if eligible)
        "successful_referrals": int,     # User.successful_referrals_count
        "max_referrals": int             # User.max_referrals
    }
    ```

**Add to OrderRepository:**
- [ ] `calculate_total_spent_by_user()`:
  - Parameters: `user_id: int`, `session: AsyncSession | Session`
  - Sum `Order.total_price` for statuses: PAID, SHIPPED, PAID_AWAITING_SHIPMENT
  - Return Decimal value

### Phase 2: Service Layer

**Add to UserService (or AdminService):**
- [ ] `get_user_list()`:
  - Parameters: `page: int = 0`, `page_size: int = 10`, `session: AsyncSession | Session`
  - Call `UserRepository.get_all_users_paginated()`
  - Format for display
  - Return formatted message + keyboard

- [ ] `get_user_detail_view()`:
  - Parameters: `user_id: int`, `session: AsyncSession | Session`
  - Fetch user via `UserRepository.get_by_id()`
  - Fetch statistics via `UserRepository.get_user_statistics()`
  - Calculate total spent via `OrderRepository.calculate_total_spent_by_user()`
  - Format detailed view message
  - Build action keyboard (dynamic based on ban status)
  - Return formatted message + keyboard

- [ ] `ban_user()`:
  - Parameters: `user_id: int`, `admin_id: int`, `reason: str`, `session: AsyncSession | Session`
  - Set `User.is_blocked = True`
  - Set `User.blocked_at = now()`
  - Set `User.blocked_reason = reason`
  - Commit changes
  - Send notification to user (optional)

- [ ] `unban_user()`:
  - Already exists, ensure it works with new flow

### Phase 3: Localization

- [ ] Add new admin strings to l10n/de.json and l10n/en.json:
  - `admin_user_list_title` ("User Management - All Users")
  - `admin_user_list_format` ("{username} - Registered: {date}")
  - `admin_user_detail_title` ("User Details")
  - `admin_user_detail_info` ("Username: {username}\nTelegram ID: {id}\nRegistered: {date}")
  - `admin_user_detail_stats` ("Statistics:\n• Total Spent: {spent}\n• Wallet: {wallet}\n• Orders: {orders}\n• Strikes: {strikes}/{max}")
  - `admin_user_detail_status` ("Status: {status}")
  - `admin_user_detail_ban_info` ("Banned: {date}\nReason: {reason}")
  - `admin_user_action_contact` ("📨 Contact User")
  - `admin_user_action_ban` ("🚫 Ban User")
  - `admin_user_action_unban` ("✅ Unban User")
  - `admin_user_action_adjust_balance` ("💰 Adjust Wallet")
  - `admin_user_action_view_orders` ("📋 View Orders")
  - `admin_user_pagination` ("Page {current}/{total}")
  - `admin_user_no_users` ("No users found")

### Phase 4: Callback Updates

**Extend UserManagementCallback:**
- [ ] Add `user_id: Optional[int] = None` (for detail view)
- [ ] Add `page: int = 0` (for pagination)
- [ ] Map new levels:
  - Level 5: User List
  - Level 6: User Detail View
  - Level 7: Ban User confirmation (optional)

### Phase 5: Handler Implementation

**Level 0: User Management Menu**
- [ ] Add new button: "View All Users" → Navigate to Level 5

**Level 5: User List (NEW)**
- [ ] Implement `show_user_list()`:
  - Read page from callback_data
  - Fetch users via `UserService.get_user_list()`
  - Build user buttons (one per user, clickable)
  - Add pagination buttons (if needed)
  - Add back button to Level 0

**Level 6: User Detail View (NEW)**
- [ ] Implement `show_user_detail()`:
  - Read user_id from callback_data
  - Fetch user details via `UserService.get_user_detail_view()`
  - Display all user information + statistics
  - Build action buttons:
    - Contact User (URL button with tg://user?id={telegram_id})
    - Ban/Unban (depending on current status)
    - Adjust Wallet (navigate to existing credit management with pre-filled user_id)
    - View Orders (navigate to Order Management filtered by user)
    - Back to User List (preserve page)

**Level 7: Ban User Confirmation (OPTIONAL)**
- [ ] Add FSM state for ban reason input
- [ ] Confirm ban action
- [ ] Call `UserService.ban_user()`
- [ ] Return to user detail view with updated status

### Phase 6: Deep Link for Contact

**Telegram Deep Link:**
- [ ] Use URL button with format: `tg://user?id={telegram_id}`
- [ ] Button text from localization: "📨 Contact User"
- [ ] This opens Telegram chat with the user directly

Example:
```python
kb_builder.button(
    text=Localizator.get_text(BotEntity.ADMIN, "admin_user_action_contact"),
    url=f"tg://user?id={user.telegram_id}"
)
```

### Phase 7: Integration with Existing Features

**Credit Management Integration:**
- [ ] Allow navigation from user detail view to credit management
- [ ] Pre-fill user_id in FSM state to skip manual input
- [ ] After balance adjustment, return to user detail view

**Order Management Integration:**
- [ ] Add "View Orders" button in user detail view
- [ ] Navigate to Order Management (Level 0) with filter: user_id={user_id}
- [ ] Requires extending Order Management with user filter (future enhancement)

### Phase 8: Testing

- [ ] User list with 0 users (edge case)
- [ ] User list with 1-10 users (single page)
- [ ] User list with 50+ users (multiple pages)
- [ ] User detail view for:
  - Active user (not banned)
  - Banned user
  - User with 0 orders (no spending)
  - User with multiple orders (spending calculated correctly)
  - User with strikes
  - User with referrals
- [ ] Contact User deep link (opens Telegram chat)
- [ ] Ban user action (with reason)
- [ ] Unban user action
- [ ] Navigation: Menu → User List → User Detail → Back to List (preserve page)
- [ ] Integration with credit management
- [ ] Total amount spent calculation accuracy

### Phase 9: Configuration

- [ ] Add to config.py:
  - `ADMIN_USERS_PER_PAGE` (default: 10)

- [ ] Document in .env.template

## Technical Notes

### Total Amount Spent Calculation

**Query:**
```python
# In OrderRepository
@staticmethod
async def calculate_total_spent_by_user(user_id: int, session: AsyncSession | Session) -> Decimal:
    query = select(func.sum(Order.total_price)).where(
        Order.user_id == user_id,
        Order.status.in_([
            OrderStatus.PAID,
            OrderStatus.SHIPPED,
            OrderStatus.PAID_AWAITING_SHIPMENT
        ])
    )
    result = await session_execute(session, query)
    total = result.scalar()
    return Decimal(total) if total else Decimal(0)
```

### Telegram Deep Link Format

- Format: `tg://user?id={telegram_id}`
- Works in Telegram clients (desktop, mobile, web)
- Opens private chat with user
- Fallback: `https://t.me/username` (if username exists)

### Ban/Unban Logic

**Ban User:**
1. Set `is_blocked = True`
2. Set `blocked_at = now()`
3. Set `blocked_reason = reason`
4. Optional: Send notification to user

**Unban User:**
1. Set `is_blocked = False`
2. Set `blocked_at = None`
3. Set `blocked_reason = None`
4. Optional: Reset strike count (configurable)

### Display Format Examples

**User List:**
```
👥 User Management - All Users

👤 @john_doe - Registered: 15.10.2024
👤 @alice123 - Registered: 20.09.2024
👤 ID:987654321 - Registered: 05.08.2024
...

[◀️ Back] [Page 1/5] [Next ▶️]
[🏠 Back to Menu]
```

**User Detail View:**
```
👤 User Details

Username: @john_doe
Telegram ID: 123456789
Registered: 15.10.2024 14:35

📊 Statistics:
• Total Spent: 450.75 EUR
• Wallet Balance: 25.50 EUR
• Successful Orders: 12
• Strikes: 1 / 3

Status: ✅ Active

🎟️ Referral Info:
• Referral Code: ABC12345
• Successful Referrals: 3 / 10

───────────────────────

[📨 Contact User]
[🚫 Ban User]
[💰 Adjust Wallet]
[📋 View Orders]

[⬅️ Back to User List]
```

**Banned User Detail:**
```
👤 User Details

Username: @banned_user
Telegram ID: 987654321
Registered: 01.05.2024 10:20

📊 Statistics:
• Total Spent: 0.00 EUR
• Wallet Balance: 0.00 EUR
• Successful Orders: 0
• Strikes: 3 / 3

Status: 🚫 BANNED
Banned: 01.11.2025 16:42
Reason: Multiple payment timeouts

───────────────────────

[📨 Contact User]
[✅ Unban User]
[💰 Adjust Wallet]
[📋 View Orders]

[⬅️ Back to User List]
```

## Benefits

- ✅ Complete user overview for admins
- ✅ Quick access to user statistics
- ✅ Easy ban/unban management
- ✅ Direct Telegram contact from admin panel
- ✅ Better user support (view spending history)
- ✅ Audit trail for user management
- ✅ Improved admin workflow efficiency

## Future Enhancements (Optional)

- User search by username/ID (search bar)
- Filter users by status (active, banned, with strikes)
- Export user list to CSV
- Bulk operations (ban multiple users)
- User activity timeline (orders, strikes, wallet transactions)
- Notes field for admins (internal comments about user)

## Dependencies

- Depends on: Order model (for total spent calculation)
- Depends on: User model (existing fields)
- Integrates with: Existing credit management
- Integrates with: Order Management (optional filter by user_id)

## Related TODOs

- `2025-11-01_TODO_order-management-pagination-filters.md` - Integration point for "View Orders" action

## Estimated Timeline

- Phase 1 (Repository): 1h
- Phase 2 (Service): 1-2h
- Phase 3 (Localization): 30min
- Phase 4 (Callbacks): 15min
- Phase 5 (Handlers): 1-2h
- Phase 6 (Deep Link): 15min
- Phase 7 (Integration): 30min
- Phase 8 (Testing): 1-2h
- Phase 9 (Config): 15min

**Total: 5-7 hours**