# Order Management System with Filtering & Pagination

**Date:** 2025-11-03
**Priority:** HIGH
**Status:** Planning
**Estimated Effort:** 4-6 hours
**Type:** Feature Enhancement

---

## Problem Statement

### Current Issues

1. **Lost Access to Order Details**
   - Admin clicks "Versendet" (Shipped) button
   - Order disappears from "Awaiting Shipment" list
   - No way to view order details, shipping address, or items anymore
   - Need to check database manually to retrieve information

2. **No Order History/Archive**
   - No way to view past orders (shipped, cancelled, completed)
   - No search or filter functionality
   - No overview of all orders in system

3. **User Has No Order History**
   - Users can't view their past orders
   - No way to check order status
   - No way to retrieve private_data from past purchases

---

## Solution Overview

**Generic Order Management System** with:
- Unified order list (Admin + User perspective)
- Filter by OrderStatus (all enum values)
- Pagination (reuse existing code)
- Detailed order view (reuse ShippingService.get_order_details_data())
- Same UI/UX as current Shipment Management

---

## Requirements

### Admin Perspective

#### Order List View
**Location:** Admin Menu → " Order Management"

**Display:**
```
 Order Management

Filter: [All Orders ▼]
Status: [All ▼] | [Pending] | [Awaiting Ship] | [Shipped] | [Cancelled]

─────────────────────────
#1234 | @username
Status: Shipped
2025-11-03 14:30 | 45.50€
[View Details →]

#1235 | @alice
Status: Awaiting Shipment
2025-11-03 12:15 | 30.00€
[View Details →]

#1236 | @bob
Status: Cancelled
2025-11-02 18:45 | 25.00€
[View Details →]
─────────────────────────

[◀ Prev] Page 1/5 [Next ▶]

[ Back to Admin Menu]
```

**Features:**
-  Paginated list (10-20 orders per page)
-  Filter by OrderStatus (dropdown with all enum values)
-  Sorted by date (newest first)
-  Shows: Order ID, Username, Status, Timestamp, Total
-  "View Details" button for each order

#### Order Details View
**Location:** Admin Menu → Order Management → View Details

**Display:** Same as current Shipment Management details view

```
 Order Details

Invoice: ORDER-2025-001234
User: @username (ID: 123456789)
Status: Shipped
Created: 2025-11-03 14:30
Paid: 2025-11-03 14:31
Shipped: 2025-11-03 15:00

─────────────────────────
Digital Items:
1x Premium Software License - Key: LICENSE-2025-ABCD
   Key: LICENSE-2025-ABCD-000001

Physical Items:
2x USB 3.0 Flash Drive - 64GB   €59.98
   €29.99 × 2

─────────────────────────
Subtotal:              €109.97
Shipping:               €5.00
═══════════════════════
Total:                 €38.15

Shipping Address:
Max Mustermann
Musterstraße 123
12345 Berlin
Germany

[ Back to Order List]
```

**Features:**
-  Full invoice display (reuse InvoiceFormatter)
-  Items with quantities (grouped)
-  Private data for digital items
-  Shipping address (if physical items)
-  All timestamps (created, paid, shipped, cancelled)
-  Payment info (wallet, crypto)
-  Refund info (if cancelled)

#### Filter Options
All OrderStatus enum values:
-  All Orders (no filter)
-   Pending Payment (`PENDING_PAYMENT`)
-  Pending Payment & Address (`PENDING_PAYMENT_AND_ADDRESS`)
-  Awaiting Shipment (`PAID_AWAITING_SHIPMENT`)
-  Shipped (`SHIPPED`)
-  Completed (`COMPLETED`)
-  Cancelled (`CANCELLED`)
-   Expired (`EXPIRED`)

---

### User Perspective

#### Order History View
**Location:** User Menu → " My Orders"

**Display:**
```
 My Orders

Filter: [All ▼] | [Active] | [Shipped] | [Completed]

─────────────────────────
Order #1234
Status:  Shipped
2025-11-03 14:30 | €45.50
[View Details →]

Order #1230
Status:  Completed
2025-10-28 10:15 | €30.00
[View Details →]

Order #1225
Status:  Cancelled
2025-10-25 16:45 | €25.00 (Refunded)
[View Details →]
─────────────────────────

[◀ Prev] Page 1/3 [Next ▶]

[ Back to Menu]
```

**Features:**
-  Paginated list (10-20 orders per page)
-  Filter: All / Active / Shipped / Completed
-  Sorted by date (newest first)
-  Shows: Order ID, Status, Timestamp, Total
-  "View Details" button

#### User Order Details
**Display:** Full invoice with items + private_data

```
 Order #1234

Invoice: ORDER-2025-001234
Status:  Shipped (2025-11-03 15:00)
Ordered: 2025-11-03 14:30

─────────────────────────
Digital Items:
1x Premium Software License
   License Key: LICENSE-2025-ABCD
   Contact Support [link]

Physical Items:
2x USB 3.0 Flash Drive - 64GB   €59.98

─────────────────────────
Subtotal:              €109.97
Shipping:               €5.00
═══════════════════════
Total:                 €38.15

Paid with Wallet: €38.15

[ Back to My Orders]
```

**Features:**
-  Full invoice display
-  Items with private_data (codes, keys)
-  Timestamps
-  Payment method
-  Refund info (if cancelled)

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────┐
│         handlers/admin/order_management.py  │
│         handlers/user/my_orders.py          │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│         services/order_management.py         │
│  - get_orders_paginated()                   │
│  - get_order_details()                      │
│  - get_filters()                            │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│         repositories/order.py                │
│  - get_orders_filtered()                    │
│  - count_orders_filtered()                  │
└─────────────────────────────────────────────┘
```

### Reusable Components

1. **Pagination:**
   - `handlers/admin/user_management.py` already has pagination (Line 41-150)
   - Copy pattern: page state, prev/next buttons, page info

2. **Order Details:**
   - `services/shipping.py::get_order_details_data()` (Line 264-318)
   - Already loads: order, items, invoice, user, shipping address
   - **Reuse as-is or extract to OrderManagementService**

3. **Invoice Formatter:**
   - `services/invoice_formatter.py::format_complete_order_view()`
   - Already handles all display modes
   - Reuse with header_type="order_details" or similar

---

## Implementation Plan

### Phase 1: Backend (2-3 hours)

#### Step 1: Repository Layer (30 min)
**File:** `repositories/order.py`

Add filtering and pagination:

```python
@staticmethod
async def get_orders_filtered(
    status_filter: OrderStatus | None = None,
    user_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession | Session
) -> list[Order]:
    """
    Get filtered orders with pagination.

    Args:
        status_filter: Filter by OrderStatus (None = all)
        user_id: Filter by user_id (None = all users, for admin)
        limit: Page size
        offset: Page offset
        session: Database session

    Returns:
        List of orders sorted by created_at DESC
    """
    stmt = (
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.invoices)
        )
        .order_by(Order.created_at.desc())
    )

    if status_filter:
        stmt = stmt.where(Order.status == status_filter)

    if user_id:
        stmt = stmt.where(Order.user_id == user_id)

    stmt = stmt.limit(limit).offset(offset)

    result = await session_execute(stmt, session)
    return result.scalars().all()


@staticmethod
async def count_orders_filtered(
    status_filter: OrderStatus | None = None,
    user_id: int | None = None,
    session: AsyncSession | Session
) -> int:
    """Count orders matching filter (for pagination)."""
    stmt = select(func.count(Order.id))

    if status_filter:
        stmt = stmt.where(Order.status == status_filter)

    if user_id:
        stmt = stmt.where(Order.user_id == user_id)

    result = await session_execute(stmt, session)
    return result.scalar_one()
```

#### Step 2: Service Layer (1 hour)
**File:** `services/order_management.py` (NEW)

```python
"""
Order Management Service

Provides order listing, filtering, and detail views for admin and users.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from enums.order_status import OrderStatus
from repositories.order import OrderRepository
from repositories.invoice import InvoiceRepository
from services.shipping import ShippingService


class OrderManagementService:

    @staticmethod
    async def get_orders_paginated(
        session: AsyncSession | Session,
        status_filter: OrderStatus | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """
        Get paginated orders with filter.

        Args:
            session: Database session
            status_filter: Filter by OrderStatus (None = all)
            user_id: Filter by user_id (None = all for admin)
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            {
                'orders': List[Order],
                'total_count': int,
                'page': int,
                'total_pages': int,
                'has_prev': bool,
                'has_next': bool
            }
        """
        offset = (page - 1) * page_size

        # Get orders and count
        orders = await OrderRepository.get_orders_filtered(
            status_filter=status_filter,
            user_id=user_id,
            limit=page_size,
            offset=offset,
            session=session
        )

        total_count = await OrderRepository.count_orders_filtered(
            status_filter=status_filter,
            user_id=user_id,
            session=session
        )

        total_pages = (total_count + page_size - 1) // page_size

        return {
            'orders': orders,
            'total_count': total_count,
            'page': page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }

    @staticmethod
    async def get_order_details(
        order_id: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Get complete order details for display.

        Reuses ShippingService.get_order_details_data() for consistency.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            Dict with order, invoice_number, username, user_id,
            shipping_address, digital_items, physical_items

        Raises:
            OrderNotFoundException: If order not found
        """
        # Reuse existing logic from ShippingService
        return await ShippingService.get_order_details_data(order_id, session)

    @staticmethod
    def get_available_filters() -> list[tuple[str, OrderStatus | None]]:
        """
        Get list of available filter options for UI.

        Returns:
            List of (display_name, status_value) tuples
        """
        return [
            (" All Orders", None),
            ("  Pending Payment", OrderStatus.PENDING_PAYMENT),
            (" Pending Payment & Address", OrderStatus.PENDING_PAYMENT_AND_ADDRESS),
            (" Awaiting Shipment", OrderStatus.PAID_AWAITING_SHIPMENT),
            (" Shipped", OrderStatus.SHIPPED),
            (" Completed", OrderStatus.COMPLETED),
            (" Cancelled", OrderStatus.CANCELLED),
            ("  Expired", OrderStatus.EXPIRED),
        ]
```

#### Step 3: Callbacks (15 min)
**File:** `callbacks.py`

Add OrderManagementCallback:

```python
class OrderManagementCallback(CallbackFactory):
    """
    Admin order management callbacks.

    Actions:
    - list: Show order list (with page, filter)
    - details: Show order details
    - filter: Change filter
    """

    action: Literal["list", "details", "filter"]
    page: int = 1
    status_filter: str | None = None  # OrderStatus.value or None
    order_id: int | None = None  # For details action
    level: int = 2  # Admin menu level
```

**File:** `callbacks.py`

Add MyOrdersCallback (for user):

```python
class MyOrdersCallback(CallbackFactory):
    """
    User order history callbacks.

    Actions:
    - list: Show my orders (with page, filter)
    - details: Show order details
    """

    action: Literal["list", "details"]
    page: int = 1
    filter: Literal["all", "active", "shipped", "completed"] = "all"
    order_id: int | None = None
    level: int = 1  # User menu level
```

---

### Phase 2: Admin UI (1-2 hours)

#### Step 1: Admin Handler (1 hour)
**File:** `handlers/admin/order_management.py` (NEW)

```python
"""
Admin Order Management Handler

Provides order list with filtering and detail views.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks import OrderManagementCallback, AdminCallback
from enums.order_status import OrderStatus
from services.order_management import OrderManagementService
from services.invoice_formatter import InvoiceFormatter
from enums.bot_entity import BotEntity
from utils.localizator import Localizator

router = Router()


@router.callback_query(OrderManagementCallback.filter(F.action == "list"))
async def show_order_list(callback: CallbackQuery, **kwargs):
    """Display paginated order list with filter."""
    session = kwargs['session']
    unpacked_cb = OrderManagementCallback.unpack(callback.data)

    # Parse status filter
    status_filter = None
    if unpacked_cb.status_filter:
        status_filter = OrderStatus[unpacked_cb.status_filter]

    # Get paginated orders
    result = await OrderManagementService.get_orders_paginated(
        session=session,
        status_filter=status_filter,
        page=unpacked_cb.page,
        page_size=20
    )

    # Build message
    if unpacked_cb.status_filter:
        filter_name = status_filter.name.replace('_', ' ').title()
        header = f" Order Management - {filter_name}"
    else:
        header = " Order Management - All Orders"

    msg = f"{header}\n\n"
    msg += f"Total: {result['total_count']} orders\n"
    msg += f"Page {result['page']}/{result['total_pages']}\n\n"
    msg += "─────────────────────────\n"

    if not result['orders']:
        msg += "No orders found.\n"
    else:
        for order in result['orders']:
            # Use eager-loaded relationships
            user = order.user
            invoices = order.invoices

            # Format user display
            if user and user.telegram_username:
                user_display = f"@{user.telegram_username}"
            elif user:
                user_display = f"ID:{user.telegram_id}"
            else:
                user_display = f"ID:{order.user_id}"

            # Format invoice display
            if invoices:
                invoice_display = invoices[0].invoice_number
            else:
                from datetime import datetime
                invoice_display = f"ORDER-{datetime.now().year}-{order.id:06d}"

            # Format status
            status_emoji = {
                OrderStatus.PENDING_PAYMENT: " ",
                OrderStatus.PENDING_PAYMENT_AND_ADDRESS: "",
                OrderStatus.PAID_AWAITING_SHIPMENT: "",
                OrderStatus.SHIPPED: "",
                OrderStatus.COMPLETED: "",
                OrderStatus.CANCELLED: "",
                OrderStatus.EXPIRED: " ",
            }.get(order.status, "")

            # Format timestamp
            created_time = order.created_at.strftime("%d.%m %H:%M") if order.created_at else "N/A"

            msg += f"{invoice_display} | {user_display}\n"
            msg += f"{status_emoji} {order.status.value} | {created_time} | €{order.total_price:.2f}\n"
            msg += "\n"

    msg += "─────────────────────────\n"

    # Build keyboard
    kb_builder = InlineKeyboardBuilder()

    # Filter buttons (2 per row)
    filters = OrderManagementService.get_available_filters()
    for i in range(0, len(filters), 2):
        row = []
        for j in range(2):
            if i + j < len(filters):
                label, status = filters[i + j]
                status_str = status.name if status else "all"
                row.append(
                    kb_builder.button(
                        text=label,
                        callback_data=OrderManagementCallback(
                            action="list",
                            page=1,
                            status_filter=status_str if status else None,
                            level=2
                        ).pack()
                    )
                )
        kb_builder.row(*row)

    # Order detail buttons (1 per row)
    for order in result['orders']:
        invoices = order.invoices
        if invoices:
            invoice_display = invoices[0].invoice_number
        else:
            from datetime import datetime
            invoice_display = f"ORDER-{datetime.now().year}-{order.id:06d}"

        kb_builder.row(
            kb_builder.button(
                text=f" View {invoice_display}",
                callback_data=OrderManagementCallback(
                    action="details",
                    order_id=order.id,
                    page=unpacked_cb.page,
                    status_filter=unpacked_cb.status_filter,
                    level=2
                ).pack()
            )
        )

    # Pagination
    if result['has_prev'] or result['has_next']:
        pagination_row = []
        if result['has_prev']:
            pagination_row.append(
                kb_builder.button(
                    text="◀ Prev",
                    callback_data=OrderManagementCallback(
                        action="list",
                        page=unpacked_cb.page - 1,
                        status_filter=unpacked_cb.status_filter,
                        level=2
                    ).pack()
                )
            )
        if result['has_next']:
            pagination_row.append(
                kb_builder.button(
                    text="Next ▶",
                    callback_data=OrderManagementCallback(
                        action="list",
                        page=unpacked_cb.page + 1,
                        status_filter=unpacked_cb.status_filter,
                        level=2
                    ).pack()
                )
            )
        kb_builder.row(*pagination_row)

    # Back button
    kb_builder.row(
        AdminCallback(action="menu", level=1).get_back_button()
    )

    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


@router.callback_query(OrderManagementCallback.filter(F.action == "details"))
async def show_order_details(callback: CallbackQuery, **kwargs):
    """Display complete order details."""
    session = kwargs['session']
    unpacked_cb = OrderManagementCallback.unpack(callback.data)

    try:
        # Get order details (reuses ShippingService logic)
        details = await OrderManagementService.get_order_details(
            unpacked_cb.order_id,
            session
        )

        # Format message using InvoiceFormatter
        msg = InvoiceFormatter.format_complete_order_view(
            header_type="admin_order_details",
            invoice_number=details['invoice_number'],
            order_status=details['order'].status,
            created_at=details['order'].created_at,
            paid_at=details['order'].paid_at,
            shipped_at=details['order'].shipped_at,
            items=details['digital_items'] + details['physical_items'],
            shipping_cost=details['order'].shipping_cost,
            total_price=details['order'].total_price,
            shipping_address=details['shipping_address'],
            username=details['username'],
            user_id=details['user_id'],
            separate_digital_physical=True,
            show_private_data=True,
            currency_symbol=Localizator.get_currency_symbol(),
            entity=BotEntity.ADMIN
        )

    except Exception as e:
        msg = f" Error loading order details: {str(e)}"

    # Build keyboard
    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(
        OrderManagementCallback(
            action="list",
            page=unpacked_cb.page,
            status_filter=unpacked_cb.status_filter,
            level=2
        ).get_back_button()
    )

    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())
```

#### Step 2: Register Handler (5 min)
**File:** `bot.py`

```python
from handlers.admin import order_management

# Register admin routers
dp.include_router(order_management.router)
```

#### Step 3: Add Menu Entry (5 min)
**File:** `handlers/admin/admin.py`

Add button to admin menu:

```python
kb_builder.button(
    text=" Order Management",
    callback_data=OrderManagementCallback(action="list", level=2).pack()
)
```

---

### Phase 3: User UI (1 hour)

#### Step 1: User Handler (45 min)
**File:** `handlers/user/my_orders.py` (NEW)

Similar structure to admin handler but:
- Filters: All / Active / Shipped / Completed (not all status types)
- Always filtered by user_id
- Simpler display (no admin actions)

```python
@router.callback_query(MyOrdersCallback.filter(F.action == "list"))
async def show_my_orders(callback: CallbackQuery, **kwargs):
    """Display user's order history."""
    session = kwargs['session']
    unpacked_cb = MyOrdersCallback.unpack(callback.data)
    user = callback.from_user

    # Map filter to status
    status_filter = None
    if unpacked_cb.filter == "active":
        # Active = pending payment or awaiting shipment
        # Need OR query - implement in repository
        pass
    elif unpacked_cb.filter == "shipped":
        status_filter = OrderStatus.SHIPPED
    elif unpacked_cb.filter == "completed":
        status_filter = OrderStatus.COMPLETED

    # Get user's orders
    result = await OrderManagementService.get_orders_paginated(
        session=session,
        user_id=user.id,
        status_filter=status_filter,
        page=unpacked_cb.page,
        page_size=15
    )

    # Build message (simpler than admin)
    msg = " My Orders\n\n"
    msg += f"Total: {result['total_count']} orders\n"
    msg += f"Page {result['page']}/{result['total_pages']}\n\n"
    msg += "─────────────────────────\n"

    for order in result['orders']:
        # ... build message ...

    # Build keyboard with filters + details buttons
    # ...
```

#### Step 2: Register Handler (5 min)
**File:** `bot.py`

```python
from handlers.user import my_orders

dp.include_router(my_orders.router)
```

#### Step 3: Add Menu Entry (5 min)
**File:** `handlers/user/my_profile.py`

Add button to user menu:

```python
kb_builder.button(
    text=" My Orders",
    callback_data=MyOrdersCallback(action="list", level=1).pack()
)
```

---

### Phase 4: Localization (30 min)

**File:** `l10n/de.json` and `l10n/en.json`

Add keys:
```json
{
  "admin": {
    "order_management_title": " Order Management",
    "order_management_all": "All Orders",
    "order_management_no_orders": "No orders found",
    "order_details_user": "User",
    "order_details_status": "Status",
    "order_details_created": "Created",
    "order_details_paid": "Paid",
    "order_details_shipped": "Shipped"
  },
  "user": {
    "my_orders_title": " My Orders",
    "my_orders_filter_all": "All",
    "my_orders_filter_active": "Active",
    "my_orders_filter_shipped": "Shipped",
    "my_orders_filter_completed": "Completed",
    "my_orders_no_orders": "You have no orders yet"
  }
}
```

---

## Testing Checklist

### Admin Order Management
- [ ] Open Order Management from admin menu
- [ ] See paginated list of all orders
- [ ] Click filter "Awaiting Shipment" → Only PAID_AWAITING_SHIPMENT orders shown
- [ ] Click filter "Shipped" → Only SHIPPED orders shown
- [ ] Click filter "All Orders" → All orders shown
- [ ] Click "View Details" on shipped order → Shows full order details including address
- [ ] Click "View Details" on cancelled order → Shows refund info
- [ ] Navigate with Prev/Next pagination → Works correctly
- [ ] Back button returns to order list (keeps page + filter state)

### User Order History
- [ ] Open "My Orders" from user menu
- [ ] See list of user's orders only
- [ ] Click "Active" filter → Only active orders
- [ ] Click "Shipped" filter → Only shipped orders
- [ ] Click "View Details" → Shows full order with private_data
- [ ] Pagination works correctly

### Edge Cases
- [ ] No orders in system → Shows "No orders found"
- [ ] Only 1 page of orders → No pagination buttons
- [ ] Filter with 0 results → Shows "No orders found"
- [ ] Order without invoice → Falls back to ORDER-YEAR-ID format

---

## Code Reuse

### From Existing Code

1. **Pagination Pattern:**
   - Source: `handlers/admin/user_management.py:41-150`
   - Pattern: Page state in callback, prev/next buttons, total pages calculation
   - **Reuse:** Copy pagination logic

2. **Order Details:**
   - Source: `services/shipping.py::get_order_details_data()`
   - Already loads: order, items, invoice, user, address, grouped items
   - **Reuse:** Call directly from OrderManagementService

3. **Invoice Display:**
   - Source: `services/invoice_formatter.py::format_complete_order_view()`
   - Already supports all order types and statuses
   - **Reuse:** Add header_type="admin_order_details" or "user_order_details"

---

## Benefits

### Admin
 **Never lose order details** - All orders accessible, even after shipped
 **Quick filtering** - Find orders by status instantly
 **Complete audit trail** - See all orders, cancelled, shipped, everything
 **Reuse existing UI** - Same details view as Shipment Management

### User
 **Order history** - View all past orders
 **Private data access** - Retrieve codes/keys from old orders
 **Order status** - Check current status of orders

### Technical
 **Code reuse** - Leverage existing pagination, details view, invoice formatter
 **Consistent UX** - Same UI patterns across admin/user
 **Scalable** - Pagination handles large order volume
 **Maintainable** - Service layer separation, clear responsibilities

---

## Implementation Priority

### Phase 1: Admin (HIGH)
Solves immediate problem: "Order details weg nach Versand"

**MVP:**
- Order list with "All" filter
- Order details view (reuse ShippingService)
- Pagination

**Estimated:** 2-3 hours

### Phase 2: Admin Filters (MEDIUM)
Enhanced filtering for better overview

**Features:**
- Status filter dropdown
- Filter by all OrderStatus enum values

**Estimated:** 1-2 hours

### Phase 3: User History (LOW)
Nice-to-have for users

**Features:**
- User order history
- Basic filters (active/shipped/completed)
- Order details with private_data

**Estimated:** 1-2 hours

---

## Security Considerations

-  Admin: Check `is_admin()` before showing order list
-  User: Always filter by user_id (can't see other users' orders)
-  Order details: Check ownership (user) or admin permission
-  Shipping addresses: Only show to admin or order owner

---

## Related TODOs

-  2025-10-24_TODO_refactor-crypto-button-generation.md (Completed)
-  2025-11-01_TODO_shipping-management-v2.md (Completed - provides order details view)
-  2025-11-01_TODO_user-management-detail-view.md (Similar pagination pattern)

---

## Success Criteria

**Admin:**
-  Can view order details after marking as shipped
-  Can filter orders by status
-  Can paginate through large order lists
-  Same UI/UX as Shipment Management

**User:**
-  Can view order history
-  Can retrieve private_data from past orders
-  Can check order status

**Technical:**
-  < 3 database queries per page (with eager loading)
-  Reuses existing components (Pagination, OrderDetails, InvoiceFormatter)
-  No code duplication

---

**Next Step:** Implement Phase 1 (Admin MVP - Order List + Details)
