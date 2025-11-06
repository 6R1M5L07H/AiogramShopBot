# Unify Order Management (Admin + User)

**Created:** 2025-11-05
**Priority:** HIGH (Code Quality / Tech Debt)
**Status:** TODO
**Estimated Effort:** 4-6 hours

## Problem Statement

### Current Redundancy

Order Management logic is **duplicated** between Admin and User implementations:

**User Order History** (`services/user.py`):
- `get_my_orders_overview()` - Filter selection
- `get_my_orders_list()` - Paginated list with filter
- `get_order_detail_for_user()` - Detail view
- ~300 lines of code

**Admin Order Management** (`handlers/admin/shipping_management.py`):
- `show_order_filter_selection()` - Filter selection
- `show_order_list()` - Paginated list with filter
- `show_order_details()` - Detail view
- ~300 lines of code

**Total Redundancy:** ~600 lines of duplicated logic

### Issues

1. **Code Duplication:** Same logic implemented twice
2. **Inconsistent UI:**
   - Admin has status emojis (📦 ✅ ❌)
   - User has NO emojis
   - Different layout formats
3. **Maintenance Burden:** Bug fixes need to be applied twice
4. **Feature Divergence:** New features only added to one side
5. **Repository Calls:** Both use `OrderRepository.get_by_user_id_with_filter()` - why duplicate the service layer?

### The Only Real Difference Should Be

```python
# User: Limited to own orders
orders = OrderRepository.get_by_user_id_with_filter(
    user_id=user.id,  # ← Specific user
    status_filter=...,
    page=...
)

# Admin: See all orders
orders = OrderRepository.get_by_user_id_with_filter(
    user_id=None,     # ← All users
    status_filter=...,
    page=...
)
```

Everything else (pagination, filtering, layout, emojis) should be IDENTICAL.

---

## Solution: Unified OrderManagementService

Create a single service that handles both Admin and User order management with configurable options.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  handlers/admin/shipping_management.py              │
│  handlers/user/my_profile.py                        │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│  services/order_management.py (NEW/REFACTORED)      │
│  - get_order_list_view()  (unified)                 │
│  - get_order_detail_view() (unified)                │
│  - get_filter_selection_view() (unified)            │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│  repositories/order.py                              │
│  - get_by_user_id_with_filter() (already unified!)  │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Create Unified Service (2-3 hours)

#### Step 1: Create/Refactor `services/order_management.py`

**Method 1: Unified Order List**

```python
class OrderManagementService:

    @staticmethod
    async def get_order_list_view(
        session: Session | AsyncSession,
        page: int = 0,
        filter_type: OrderFilterType | None = None,
        user_id: int | None = None,  # None = Admin (all), specific = User (limited)
        entity: BotEntity = BotEntity.USER,
        callback_factory: type = MyProfileCallback,  # MyProfileCallback or ShippingManagementCallback
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Unified order list for both Admin and User.

        Args:
            session: Database session
            page: Page number (0-indexed)
            filter_type: OrderFilterType enum value (None = ALL)
            user_id: None for admin (all orders), specific ID for user (own orders)
            entity: BotEntity.ADMIN or BotEntity.USER (for localization)
            callback_factory: Callback class to use for navigation

        Returns:
            Tuple of (message_text, keyboard_builder)
        """
        from enums.order_filter import OrderFilterType
        from utils.order_filters import get_status_filter_for_user, get_status_filter_for_admin
        from repositories.order import OrderRepository
        from datetime import datetime

        # Get status filter (admin vs user have different filter logic)
        if user_id is None:
            # Admin: use admin filter logic
            status_filter = get_status_filter_for_admin(filter_type)
        else:
            # User: use user filter logic
            status_filter = get_status_filter_for_user(filter_type)

        # Get orders with pagination
        orders = await OrderRepository.get_by_user_id_with_filter(
            user_id=user_id,  # None = all users (admin), specific = one user
            status_filter=status_filter,
            page=page,
            session=session
        )

        # Get max page for pagination
        max_page = await OrderRepository.get_max_page_by_user_id(
            user_id=user_id,
            status_filter=status_filter,
            session=session
        )

        # Determine filter name for display
        filter_name = OrderManagementService._get_filter_display_name(
            filter_type, entity
        )

        # Build message header
        message_text = Localizator.get_text(entity, "order_list_title") + "\n"
        message_text += Localizator.get_text(entity, "order_filter_current").format(
            filter_name=filter_name
        ) + "\n\n"

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()

        if not orders:
            message_text += Localizator.get_text(entity, "order_no_orders")
        else:
            # Add order buttons with CONSISTENT layout (with emojis!)
            for order in orders:
                # Status emoji (BOTH admin and user get emojis now!)
                emoji = OrderManagementService._get_status_emoji(order.status)

                # Short date: DD.MM (without year)
                created_time = order.created_at.strftime("%d.%m")

                # Short invoice: last 6 chars
                full_invoice = order.invoices[0].invoice_number if order.invoices else f"ORDER-{datetime.now().year}-{order.id:06d}"
                short_invoice = full_invoice[-6:]

                # Get status text
                status_text = Localizator.get_text(BotEntity.COMMON, f"order_status_{order.status.value}")

                # Unified button layout: "📦 DD.MM • SHORT_ID • Status"
                button_text = f"{emoji} {created_time} • {short_invoice} • {status_text}".ljust(40)

                kb_builder.button(
                    text=button_text,
                    callback_data=callback_factory.create(
                        level=9 if user_id else 2,  # Level depends on context
                        filter_type=filter_type,
                        args_for_action=order.id if user_id else None,
                        order_id=order.id if not user_id else -1
                    ).pack()
                )

            # Single column layout
            kb_builder.adjust(1)

        # Add pagination
        if max_page > 0:
            pagination_row = []
            if page > 0:
                pagination_row.append(
                    types.InlineKeyboardButton(
                        text="◀️ Zurück",
                        callback_data=callback_factory.create(
                            level=8 if user_id else 1,
                            filter_type=filter_type,
                            page=page-1
                        ).pack()
                    )
                )
            if page < max_page:
                pagination_row.append(
                    types.InlineKeyboardButton(
                        text="Weiter ▶️",
                        callback_data=callback_factory.create(
                            level=8 if user_id else 1,
                            filter_type=filter_type,
                            page=page+1
                        ).pack()
                    )
                )
            if pagination_row:
                kb_builder.row(*pagination_row)

        # Filter change button
        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(entity, "order_filter_change_button"),
                callback_data=callback_factory.create(
                    level=10 if user_id else 0
                ).pack()
            )
        )

        # Back button
        back_level = 0  # Back to profile (user) or admin menu (admin)
        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=callback_factory.create(level=back_level).pack()
            )
        )

        return message_text, kb_builder

    @staticmethod
    def _get_status_emoji(status: OrderStatus) -> str:
        """Get emoji for order status (consistent for admin and user)"""
        from enums.order_status import OrderStatus

        STATUS_EMOJI_MAP = {
            OrderStatus.PENDING_PAYMENT: "⏳",
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS: "📝",
            OrderStatus.PENDING_PAYMENT_PARTIAL: "⚠️",
            OrderStatus.PAID: "✅",
            OrderStatus.PAID_AWAITING_SHIPMENT: "📦",
            OrderStatus.SHIPPED: "🚚",
            OrderStatus.CANCELLED_BY_USER: "❌",
            OrderStatus.CANCELLED_BY_ADMIN: "🚫",
            OrderStatus.CANCELLED_BY_SYSTEM: "⛔",
            OrderStatus.TIMEOUT: "⏰",
        }

        return STATUS_EMOJI_MAP.get(status, "📄")

    @staticmethod
    def _get_filter_display_name(
        filter_type: int | None,
        entity: BotEntity
    ) -> str:
        """Get display name for filter"""
        from enums.order_filter import OrderFilterType

        if filter_type is None:
            return Localizator.get_text(entity, "order_filter_all")
        elif filter_type == OrderFilterType.ACTIVE:
            return Localizator.get_text(entity, "order_filter_active")
        elif filter_type == OrderFilterType.COMPLETED:
            return Localizator.get_text(entity, "order_filter_completed_user" if entity == BotEntity.USER else "order_filter_completed")
        elif filter_type == OrderFilterType.CANCELLED:
            return Localizator.get_text(entity, "order_filter_cancelled_user" if entity == BotEntity.USER else "order_filter_cancelled")
        else:
            return Localizator.get_text(entity, "order_filter_all")

    @staticmethod
    async def get_order_detail_view(
        order_id: int,
        session: Session | AsyncSession,
        user_id: int | None = None,  # For ownership check (user only)
        entity: BotEntity = BotEntity.USER,
        callback_factory: type = MyProfileCallback,
        filter_type: int | None = None,
        page: int = 0
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Unified order detail view for both Admin and User.

        Args:
            order_id: Order ID
            session: Database session
            user_id: User ID for ownership check (user only, None for admin)
            entity: BotEntity.ADMIN or BotEntity.USER
            callback_factory: Callback class for navigation
            filter_type: Current filter (for back button)
            page: Current page (for back button)

        Returns:
            Tuple of (message_text, keyboard_builder)

        Raises:
            OrderNotFoundException: If order not found or doesn't belong to user
        """
        from services.shipping import ShippingService
        from services.invoice_formatter import InvoiceFormatter
        from exceptions.order import OrderNotFoundException
        from repositories.user import UserRepository

        # Get order details (reuses existing logic)
        try:
            order_data = await ShippingService.get_order_details_data(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        order = order_data["order"]

        # SECURITY: Verify ownership if user context
        if user_id is not None:
            user = await UserRepository.get_by_tgid(user_id, session)
            if order.user_id != user.id:
                raise OrderNotFoundException(order_id)

        # Build items list
        items_list = []

        # Digital items
        for (description, price), quantity in order_data["digital_items"].items():
            items_list.append({
                'name': description,
                'price': price,
                'quantity': quantity,
                'is_physical': False,
            })

        # Physical items
        for (description, price), quantity in order_data["physical_items"].items():
            items_list.append({
                'name': description,
                'price': price,
                'quantity': quantity,
                'is_physical': True,
            })

        # Calculate subtotal
        subtotal = order.total_price - order.shipping_cost

        # Format message (unified display)
        msg = InvoiceFormatter.format_complete_order_view(
            header_type="order_detail_admin" if entity == BotEntity.ADMIN else "order_detail_user",
            invoice_number=order_data["invoice_number"],
            order_status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            items=items_list,
            subtotal=subtotal,
            shipping_cost=order.shipping_cost,
            total_price=order.total_price,
            separate_digital_physical=True,
            show_private_data=(entity == BotEntity.ADMIN),  # Admin sees private data
            show_retention_notice=False,
            currency_symbol=Localizator.get_currency_symbol(),
            entity=entity
        )

        # Add shipping address if exists
        if order_data["shipping_address"]:
            if entity == BotEntity.ADMIN or not order_data["shipping_address"].startswith("[DECRYPTION FAILED"):
                import config
                msg += f"\n\n📬 <b>{Localizator.get_text(entity, 'shipping_address_label')}:</b>\n"
                if not order_data["shipping_address"].startswith("[DECRYPTION FAILED"):
                    msg += f"<code>{order_data['shipping_address']}</code>\n"
                if entity == BotEntity.USER:
                    msg += f"<i>{Localizator.get_text(entity, 'shipping_address_encrypted_notice').format(retention_days=config.DATA_RETENTION_DAYS)}</i>"

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()

        # Admin: Show action buttons (Mark as Shipped, Cancel, etc.)
        if entity == BotEntity.ADMIN:
            # Context-aware buttons based on order status
            from enums.order_status import OrderStatus

            # Mark as Shipped (only for PAID_AWAITING_SHIPMENT)
            if order.status == OrderStatus.PAID_AWAITING_SHIPMENT:
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.ADMIN, "mark_as_shipped"),
                    callback_data=callback_factory.create(
                        level=3,
                        order_id=order_id,
                        filter_type=filter_type,
                        page=page
                    ).pack()
                )

            # Cancel Order (if allowed)
            if order.status not in [OrderStatus.SHIPPED, OrderStatus.CANCELLED_BY_ADMIN, OrderStatus.CANCELLED_BY_USER, OrderStatus.CANCELLED_BY_SYSTEM]:
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.ADMIN, "cancel_order"),
                    callback_data=callback_factory.create(
                        level=4,
                        order_id=order_id,
                        filter_type=filter_type,
                        page=page
                    ).pack()
                )

        # Back button
        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=callback_factory.create(
                    level=8 if user_id else 1,
                    filter_type=filter_type,
                    page=page
                ).pack()
            )
        )

        return msg, kb_builder
```

#### Step 2: Update Existing Utilities

Ensure `utils/order_filters.py` has both admin and user filter logic:

```python
# utils/order_filters.py

def get_status_filter_for_admin(filter_type: int | None) -> list[OrderStatus] | None:
    """Get status filter for admin view"""
    # ... existing admin logic ...

def get_status_filter_for_user(filter_type: int | None) -> list[OrderStatus] | None:
    """Get status filter for user view"""
    # ... existing user logic ...
```

---

### Phase 2: Refactor User Implementation (1 hour)

#### Update `services/user.py`

**Before (~300 lines):**
```python
async def get_my_orders_list(...):
    # 100+ lines of duplicated logic
    ...
```

**After (~30 lines):**
```python
@staticmethod
async def get_my_orders_list(
    telegram_id: int,
    filter_type: int | None,
    page: int,
    session: Session | AsyncSession
) -> tuple[str, InlineKeyboardBuilder]:
    """Get user's order list (wrapper around unified service)"""
    from services.order_management import OrderManagementService
    from repositories.user import UserRepository

    user = await UserRepository.get_by_tgid(telegram_id, session)

    return await OrderManagementService.get_order_list_view(
        session=session,
        page=page,
        filter_type=filter_type,
        user_id=user.id,  # ← User-specific
        entity=BotEntity.USER,
        callback_factory=MyProfileCallback
    )

@staticmethod
async def get_order_detail_for_user(
    order_id: int,
    telegram_id: int,
    session: Session | AsyncSession,
    filter_type: int | None = None
) -> tuple[str, InlineKeyboardBuilder]:
    """Get order detail (wrapper around unified service)"""
    from services.order_management import OrderManagementService

    return await OrderManagementService.get_order_detail_view(
        order_id=order_id,
        session=session,
        user_id=telegram_id,  # ← Ownership check
        entity=BotEntity.USER,
        callback_factory=MyProfileCallback,
        filter_type=filter_type
    )
```

**Delete old methods:**
- ❌ `get_my_orders_list()` implementation (keep wrapper)
- ❌ `get_order_detail_for_user()` implementation (keep wrapper)

---

### Phase 3: Refactor Admin Implementation (1 hour)

#### Update `handlers/admin/shipping_management.py`

**Before (~300 lines):**
```python
async def show_order_list(...):
    # 100+ lines of duplicated logic
    ...
```

**After (~30 lines):**
```python
async def show_order_list(**kwargs):
    """Level 1: Order list with filter (wrapper around unified service)"""
    from services.order_management import OrderManagementService

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    filter_type = callback_data.filter_type if callback_data else None
    page = callback_data.page if callback_data else 0

    message_text, kb_builder = await OrderManagementService.get_order_list_view(
        session=session,
        page=page,
        filter_type=filter_type,
        user_id=None,  # ← Admin sees all
        entity=BotEntity.ADMIN,
        callback_factory=ShippingManagementCallback
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())

async def show_order_details(**kwargs):
    """Level 2: Order details (wrapper around unified service)"""
    from services.order_management import OrderManagementService

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id
    filter_type = callback_data.filter_type if callback_data else None
    page = callback_data.page if callback_data else 0

    try:
        message_text, kb_builder = await OrderManagementService.get_order_detail_view(
            order_id=order_id,
            session=session,
            user_id=None,  # ← Admin, no ownership check
            entity=BotEntity.ADMIN,
            callback_factory=ShippingManagementCallback,
            filter_type=filter_type,
            page=page
        )
        await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())
    except OrderNotFoundException:
        # Show error and return to list
        error_text = Localizator.get_text(BotEntity.ADMIN, "error_order_not_found")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=1, filter_type=filter_type, page=page).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
```

**Delete old methods:**
- ❌ `show_order_list()` implementation (keep wrapper)
- ❌ `show_order_details()` implementation (keep wrapper)

---

### Phase 4: Add Emojis to User View (15 minutes)

This is now **automatically included** in the unified service!

Users will now see:
```
📦 03.11 • 85TQ2A • Bezahlt (Versand ausstehend)
✅ 02.11 • H8Y8J4 • Versendet
❌ 01.11 • DG5WA • Storniert
```

Instead of:
```
03.11 • 85TQ2A • Bezahlt (Versand ausstehend)
02.11 • H8Y8J4 • Versendet
01.11 • DG5WA • Storniert
```

---

### Phase 5: Testing (1-2 hours)

#### User Order History Tests
- [ ] User sees own orders only (not other users')
- [ ] User sees emojis in order list
- [ ] Filter change works (All, Completed, Cancelled)
- [ ] Pagination works
- [ ] Order detail view works
- [ ] Ownership verification prevents unauthorized access
- [ ] Back button preserves filter + page

#### Admin Order Management Tests
- [ ] Admin sees all orders (all users)
- [ ] Admin sees emojis in order list (same as user)
- [ ] Filter change works (All, Active, Completed, Cancelled)
- [ ] Pagination works
- [ ] Order detail view works
- [ ] Admin action buttons shown correctly
- [ ] Back button preserves filter + page

#### Consistency Tests
- [ ] Layout identical between admin and user
- [ ] Emojis identical between admin and user
- [ ] Order detail format identical (except private_data visibility)
- [ ] Pagination behavior identical

#### Edge Cases
- [ ] Empty order list (user with no orders)
- [ ] Single page (1-10 orders)
- [ ] Multiple pages (50+ orders)
- [ ] Filter with 0 results
- [ ] Order detail for missing order (404 handling)

---

## Benefits

### Code Quality
- ✅ **-300 lines of code** (50% reduction)
- ✅ **Single source of truth** for order management
- ✅ **DRY principle** applied correctly
- ✅ **Easier to maintain** (bug fixes only once)

### Consistency
- ✅ **Identical UI** for admin and user
- ✅ **Emojis for both** (better UX)
- ✅ **Same pagination logic**
- ✅ **Same layout format**

### Maintainability
- ✅ **New features** automatically work for both
- ✅ **Bug fixes** only need to be applied once
- ✅ **Testing** simplified (test once, not twice)
- ✅ **Refactoring** easier in future

### User Experience
- ✅ **Users get emojis** (visual improvement)
- ✅ **Consistent behavior** across admin/user
- ✅ **Better UX parity** (admin and user feel consistent)

---

## Migration Notes

- **No database changes needed** (pure refactoring)
- **No breaking changes** (external behavior identical)
- **Callbacks remain the same** (MyProfileCallback, ShippingManagementCallback)
- **Localization keys remain the same** (no l10n changes)

---

## Estimated Timeline

- Phase 1 (Unified Service): 2-3h
- Phase 2 (User Refactor): 1h
- Phase 3 (Admin Refactor): 1h
- Phase 4 (Emojis): 15min (automatic)
- Phase 5 (Testing): 1-2h

**Total: 5-7 hours**

---

## Success Criteria

- ✅ Code reduced by ~300 lines (50%)
- ✅ Both admin and user use `OrderManagementService`
- ✅ User sees emojis in order list
- ✅ All tests pass (user and admin)
- ✅ No behavioral changes (refactoring only)
- ✅ Consistent UI between admin and user
