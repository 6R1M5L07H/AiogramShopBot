"""
Order Management Service

Unified service for both Admin and User order management.
Eliminates code duplication between:
- Admin Order Management (handlers/admin/shipping_management.py)
- User Order History (services/user.py)

Single source of truth for:
- Order list views (with pagination and filtering)
- Order detail views
- Status emoji mapping
- Filter display names

Usage:
    # User context
    OrderManagementService.get_order_list_view(
        user_id=123,  # Limited to one user
        entity=BotEntity.USER
    )

    # Admin context
    OrderManagementService.get_order_list_view(
        user_id=None,  # All users
        entity=BotEntity.ADMIN
    )
"""

from typing import Optional
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from enums.bot_entity import BotEntity
from enums.order_status import OrderStatus
from enums.order_filter import OrderFilterType
from utils.localizator import Localizator
from callbacks import MyProfileCallback, ShippingManagementCallback


class OrderManagementService:
    """Unified order management for Admin and User"""

    # Status emoji mapping (consistent across admin and user)
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

    @staticmethod
    async def get_order_list_view(
        session: Session | AsyncSession,
        page: int = 0,
        filter_type: OrderFilterType | int | None = None,
        user_id: int | None = None,
        entity: BotEntity = BotEntity.USER,
        callback_factory: type = MyProfileCallback,
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Unified order list for both Admin and User.

        Args:
            session: Database session
            page: Page number (0-indexed)
            filter_type: OrderFilterType enum value (None = ALL/default)
            user_id: None for admin (all orders), specific ID for user (own orders)
            entity: BotEntity.ADMIN or BotEntity.USER (for localization)
            callback_factory: MyProfileCallback or ShippingManagementCallback

        Returns:
            Tuple of (message_text, keyboard_builder)
        """
        from utils.order_filters import get_status_filter_for_user, get_status_filter_for_filter_type
        from repositories.order import OrderRepository

        # Get status filter (different logic for admin vs user)
        if user_id is None:
            # Admin: use admin/general filter logic
            status_filter = get_status_filter_for_filter_type(filter_type)
        else:
            # User: use user-specific filter logic
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

                # Full invoice number (e.g., INV-2025-ABCDEF)
                # Fallback to Order ID if no invoice exists (old orders or data migration issues)
                invoice_number = order.invoices[0].invoice_number if order.invoices else f"Order-{order.id}"

                # Get status text
                status_text = Localizator.get_text(BotEntity.COMMON, f"order_status_{order.status.value}")

                # Unified button layout: "📦 DD.MM • INV-YYYY-XXXXXX • Status"
                button_text = f"{emoji} {created_time} • {invoice_number} • {status_text}"

                # Build callback data (different levels for user vs admin)
                if user_id:
                    # User: Level 9 (order detail)
                    callback_data = callback_factory.create(
                        level=9,
                        filter_type=filter_type,
                        args_for_action=order.id
                    ).pack()
                else:
                    # Admin: Level 2 (order detail)
                    callback_data = callback_factory.create(
                        level=2,
                        order_id=order.id,
                        filter_type=filter_type,
                        page=page
                    ).pack()

                kb_builder.button(
                    text=button_text,
                    callback_data=callback_data
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
                    level=10 if user_id else 0,
                    filter_type=filter_type
                ).pack()
            )
        )

        # Back button
        back_level = 0  # Back to profile (user) or admin menu (admin)
        from callbacks import AdminMenuCallback

        if user_id:
            # User: back to My Profile
            back_callback = callback_factory.create(level=back_level).pack()
        else:
            # Admin: back to Admin Menu
            back_callback = AdminMenuCallback.create(level=0).pack()

        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=back_callback
            )
        )

        return message_text, kb_builder

    @staticmethod
    async def get_order_detail_view(
        order_id: int,
        session: Session | AsyncSession,
        user_id: int | None = None,
        telegram_id: int | None = None,
        entity: BotEntity = BotEntity.USER,
        callback_factory: type = MyProfileCallback,
        filter_type: OrderFilterType | int | None = None,
        page: int = 0
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Unified order detail view for both Admin and User.

        Args:
            order_id: Order ID
            session: Database session
            user_id: User DB ID for ownership check (user only, None for admin)
            telegram_id: Telegram ID for user context (alternative to user_id)
            entity: BotEntity.ADMIN or BotEntity.USER
            callback_factory: MyProfileCallback or ShippingManagementCallback
            filter_type: Current filter (for back button)
            page: Current page (for back button)

        Returns:
            Tuple of (message_text, keyboard_builder)

        Raises:
            OrderNotFoundException: If order not found or doesn't belong to user
        """
        from services.shipping import ShippingService
        from services.invoice_formatter import InvoiceFormatterService
        from exceptions.order import OrderNotFoundException
        from repositories.user import UserRepository

        # Get order details (reuses existing logic)
        try:
            order_data = await ShippingService.get_order_details_data(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        order = order_data["order"]

        # SECURITY: Verify ownership if user context
        if user_id is not None or telegram_id is not None:
            if telegram_id is not None:
                user = await UserRepository.get_by_tgid(telegram_id, session)
                user_id = user.id
            if order.user_id != user_id:
                raise OrderNotFoundException(order_id)

        # Get actual items with private_data for User context
        from repositories.item import ItemRepository
        from repositories.subcategory import SubcategoryRepository
        from services.order import OrderService
        from enums.order_status import OrderStatus
        import json

        # Check if order is cancelled - if so, use items_snapshot instead of items table
        is_cancelled = order.status in [
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.TIMEOUT
        ]

        if is_cancelled and order.items_snapshot:
            # Use items snapshot (items were released back to stock)
            logging.info(f"Order {order_id} is cancelled - using items_snapshot")
            snapshot_items = json.loads(order.items_snapshot)

            # Load refund breakdown if available (for mixed orders)
            refund_breakdown = None
            if order.refund_breakdown_json:
                try:
                    refund_breakdown = json.loads(order.refund_breakdown_json)
                    logging.info(f"Order {order_id} has refund breakdown: is_mixed={refund_breakdown.get('is_mixed_order')}")
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse refund_breakdown_json for order {order_id}")

            # Build items_raw from snapshot
            items_raw = []
            for snapshot_item in snapshot_items:
                items_raw.append({
                    'name': snapshot_item['description'],
                    'price': snapshot_item['price'],
                    'quantity': snapshot_item['quantity'],
                    'is_physical': snapshot_item['is_physical'],
                    'private_data': snapshot_item.get('private_data'),
                    'tier_breakdown': None  # Tier breakdown not stored in snapshot
                })

            # Group items for display
            items_list = OrderService._group_items_for_display(items_raw)

            # Calculate subtotal
            subtotal = order.total_price - order.shipping_cost

            # Check if any items have private_data
            has_private_data = any(item.get('private_data') for item in snapshot_items)

        else:
            # Active order - get items from database
            order_items = await ItemRepository.get_by_order_id(order_id, session)

            # Parse tier breakdown from order (NO recalculation!)
            tier_breakdown_list = OrderService._parse_tier_breakdown_from_order(order)

            # Get subcategory information
            subcategory_ids = list({item.subcategory_id for item in order_items})
            subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

            # Fallback: If tier_breakdown_json not available (old orders), recalculate
            if not tier_breakdown_list:
                logging.warning(f"Order {order_id} has no tier_breakdown_json, falling back to recalculation")
                tier_breakdown_list = await OrderService._group_items_with_tier_pricing(
                    order_items, subcategories_dict, session
                )

            # Build items list with private_data (ungrouped for individual keys/codes)
            items_raw = []
            for item in order_items:
                # Find corresponding tier breakdown from tier_breakdown_list
                tier_breakdown = None
                for tier_item in tier_breakdown_list:
                    subcategory = subcategories_dict.get(item.subcategory_id)
                    if subcategory and tier_item['subcategory_name'] == subcategory.name:
                        tier_breakdown = tier_item.get('breakdown')
                        break

                items_raw.append({
                    'name': item.description,
                    'price': item.price,
                    'quantity': 1,  # Each item is already individual
                    'is_physical': item.is_physical,
                    'private_data': item.private_data,
                    'tier_breakdown': tier_breakdown if not item.private_data else None  # Don't show tier breakdown for individual items with codes
                })

            # Group items by (name, price, is_physical, private_data) while preserving tier_breakdown
            items_list = OrderService._group_items_for_display(items_raw)

            # Calculate subtotal
            subtotal = order.total_price - order.shipping_cost

            # Check if any items have private_data (for retention notice)
            has_private_data = any(item.private_data for item in order_items)

            # No refund breakdown for active orders
            refund_breakdown = None

        # Get shipping type name for display
        shipping_type_name = None
        if order.shipping_type_key:
            from utils.shipping_types_loader import load_shipping_types, get_shipping_type
            try:
                shipping_types = load_shipping_types("de")
                shipping_type = get_shipping_type(shipping_types, order.shipping_type_key)
                if shipping_type:
                    shipping_type_name = shipping_type.get("name")
            except Exception:
                logging.warning(f"Failed to load shipping type for key: {order.shipping_type_key}")

        # Format message (unified display)
        msg = InvoiceFormatterService.format_complete_order_view(
            header_type="order_detail_admin" if entity == BotEntity.ADMIN else "order_detail_user",
            invoice_number=order_data["invoice_number"],
            order_status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            items=items_list,
            subtotal=subtotal,
            shipping_cost=order.shipping_cost,
            shipping_type_name=shipping_type_name,  # Pass shipping type name
            total_price=order.total_price,
            wallet_used=order.wallet_used,  # Pass wallet usage for display
            separate_digital_physical=True,
            show_private_data=True,  # Show keys/codes for both Admin and User
            show_retention_notice=has_private_data and (entity == BotEntity.USER),  # Only show retention notice to users
            cancellation_reason=order.cancellation_reason,  # Pass stored cancellation reason
            partial_refund_info=refund_breakdown,  # Refund breakdown for mixed order cancellations
            currency_symbol=Localizator.get_currency_symbol(),
            entity=entity
        )

        # Add shipping address if exists
        if order_data["shipping_address"]:
            import config
            if entity == BotEntity.ADMIN:
                # Admin: Show actual decrypted address
                msg += f"\n\n📬 <b>{Localizator.get_text(entity, 'shipping_address_label')}:</b>\n"
                if not order_data["shipping_address"].startswith("[DECRYPTION FAILED"):
                    msg += f"<code>{order_data['shipping_address']}</code>\n"
                else:
                    msg += f"<i>{order_data['shipping_address']}</i>\n"
            else:
                # User: Only show encrypted notice, NOT the address itself
                msg += f"\n\n📬 <b>{Localizator.get_text(entity, 'shipping_address_label')}:</b>\n"
                msg += f"<i>{Localizator.get_text(entity, 'shipping_address_encrypted_notice').format(retention_days=config.DATA_RETENTION_DAYS)}</i>"

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()

        # Admin: Show action buttons (Mark as Shipped, Cancel, etc.)
        if entity == BotEntity.ADMIN:
            # Context-aware buttons based on order status

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
            if order.status not in [
                OrderStatus.SHIPPED,
                OrderStatus.CANCELLED_BY_ADMIN,
                OrderStatus.CANCELLED_BY_USER,
                OrderStatus.CANCELLED_BY_SYSTEM
            ]:
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.ADMIN, "cancel_order"),
                    callback_data=callback_factory.create(
                        level=4,
                        order_id=order_id,
                        filter_type=filter_type,
                        page=page
                    ).pack()
                )

        # User: Show Cancel Order button for pending orders
        elif entity == BotEntity.USER:
            # Cancel Order (if allowed)
            if order.status in [
                OrderStatus.PENDING_PAYMENT,
                OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
                OrderStatus.PENDING_PAYMENT_PARTIAL
            ]:
                # Use OrderCallback for user cancellation (not MyProfileCallback)
                from callbacks import OrderCallback
                cancel_callback_data = OrderCallback.create(level=4, order_id=order_id).pack()
                logging.info(f"🟢 Creating Cancel Order button with callback_data: {cancel_callback_data}")
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.USER, "cancel_order"),
                    callback_data=cancel_callback_data
                )

        # Back button
        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=callback_factory.create(
                    level=8 if (user_id or telegram_id) else 1,
                    filter_type=filter_type,
                    page=page
                ).pack()
            )
        )

        return msg, kb_builder

    @staticmethod
    def _get_status_emoji(status: OrderStatus) -> str:
        """Get emoji for order status (consistent for admin and user)"""
        return OrderManagementService.STATUS_EMOJI_MAP.get(status, "📄")

    @staticmethod
    def _get_filter_display_name(
        filter_type: OrderFilterType | int | None,
        entity: BotEntity
    ) -> str:
        """Get display name for filter"""

        if filter_type is None:
            if entity == BotEntity.ADMIN:
                # Admin: None = REQUIRES_ACTION (default)
                return Localizator.get_text(entity, "order_filter_requires_action")
            else:
                # User: None = ALL
                return Localizator.get_text(entity, "order_filter_all")
        elif filter_type == OrderFilterType.ALL:
            return Localizator.get_text(entity, "order_filter_all")
        elif filter_type == OrderFilterType.ACTIVE:
            return Localizator.get_text(entity, "order_filter_active")
        elif filter_type == OrderFilterType.REQUIRES_ACTION:
            return Localizator.get_text(entity, "order_filter_requires_action")
        elif filter_type == OrderFilterType.COMPLETED:
            if entity == BotEntity.USER:
                return Localizator.get_text(entity, "order_filter_completed_user")
            else:
                return Localizator.get_text(entity, "order_filter_completed")
        elif filter_type == OrderFilterType.CANCELLED:
            if entity == BotEntity.USER:
                return Localizator.get_text(entity, "order_filter_cancelled_user")
            else:
                return Localizator.get_text(entity, "order_filter_cancelled")
        else:
            # Fallback
            return Localizator.get_text(entity, "order_filter_all")
