from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks import AdminMenuCallback
from enums.bot_entity import BotEntity
from handlers.common.common import add_pagination_buttons
from repositories.order import OrderRepository
from repositories.user import UserRepository
from services.order import OrderService
from utils.localizator import Localizator

router = Router()


@router.callback_query(AdminMenuCallback.filter(F.action == "order_management"))
async def show_order_management_menu(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Show order management main menu"""
    kb_builder = InlineKeyboardBuilder()
    
    # Orders ready for shipment
    kb_builder.button(text="📦 Orders Ready for Shipment", 
                      callback_data=AdminMenuCallback.create(level=0, action="orders_ready_shipment", page=0))
    
    # Search users by timeout count
    kb_builder.button(text="⏰ Users with Timeouts", 
                      callback_data=AdminMenuCallback.create(level=0, action="users_timeouts", page=0))
    
    # Manual cleanup orders
    kb_builder.button(text="🧹 Run Cleanup", 
                      callback_data=AdminMenuCallback.create(level=0, action="manual_cleanup"))
    
    # Back to admin menu
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminMenuCallback.create(level=0, action="admin_panel"))
    
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text="📦 Order Management\n\nSelect an option:",
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminMenuCallback.filter(F.action == "orders_ready_shipment"))
async def show_orders_ready_for_shipment(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Show orders that are ready for shipment"""
    total_orders = await OrderRepository.get_orders_ready_for_shipment_count()
    if total_orders == 0:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back",
                          callback_data=AdminMenuCallback.create(level=0, action="order_management"))
        await callback.message.edit_text(
            text="No orders ready for shipment.",
            reply_markup=kb_builder.as_markup()
        )
        return

    page = callback_data.page
    orders = await OrderRepository.get_orders_ready_for_shipment(page)
    kb_builder = InlineKeyboardBuilder()

    for order in orders:
        user = await UserRepository.get_user_entity(order.user_id)
        user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"

        kb_builder.button(
            text=f"Order #{order.id} - {user_info} - {order.total_amount} {order.currency}",
            callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order.id)
        )

    kb_builder.adjust(1)
    back_button = AdminMenuCallback.create(level=0, action="order_management").get_back_button(0)
    kb_builder = await add_pagination_buttons(kb_builder, callback_data,
                                              OrderRepository.get_orders_ready_for_shipment_max_page(),
                                              back_button)

    await callback.message.edit_text(
        text=f"📦 Orders Ready for Shipment ({total_orders} total):",
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminMenuCallback.filter(F.action == "view_order"))
async def view_order_details(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """View detailed order information"""
    order_id = int(callback_data.args_to_action)
    order = await OrderRepository.get_by_id(order_id)
    
    if not order:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminMenuCallback.create(level=0, action="orders_ready_shipment", page=0))
        
        await callback.message.edit_text(
            text="Order not found.",
            reply_markup=kb_builder.as_markup()
        )
        return
    
    user = await UserRepository.get_user_entity(order.user_id)
    user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID: {user.telegram_id}"
    
    message_text = f"""📦 Order Details

Order ID: #{order.id}
User: {user_info}
Status: {order.status.upper()}
Amount: {order.total_amount} {order.currency}
Payment Address: {order.payment_address}
Created: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}"""
    
    if order.paid_at:
        message_text += f"\nPaid: {order.paid_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    if order.shipped_at:
        message_text += f"\nShipped: {order.shipped_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    kb_builder = InlineKeyboardBuilder()
    
    if order.status == "paid":
        kb_builder.button(text="✅ Mark as Shipped", 
                          callback_data=AdminMenuCallback.create(level=0, action="ship_order", args_to_action=order.id))
        kb_builder.button(text="🔐 Access Private Key", 
                          callback_data=AdminMenuCallback.create(level=0, action="access_private_key", args_to_action=order.id))
    
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminMenuCallback.create(level=0, action="orders_ready_shipment", page=0))
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminMenuCallback.filter(F.action == "ship_order"))
async def mark_order_as_shipped(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Mark order as shipped"""
    order_id = int(callback_data.args_to_action)
    admin_id = callback.from_user.id
    
    try:
        await OrderService.ship_order(order_id, admin_id)
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back to Orders", 
                          callback_data=AdminMenuCallback.create(level=0, action="orders_ready_shipment", page=0))
        
        await callback.message.edit_text(
            text=f"✅ Order #{order_id} has been marked as shipped!\nUser has been notified.",
            reply_markup=kb_builder.as_markup()
        )
        
    except Exception as e:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order_id))
        
        await callback.message.edit_text(
            text=f"❌ Error shipping order: {str(e)}",
            reply_markup=kb_builder.as_markup()
        )


@router.callback_query(AdminMenuCallback.filter(F.action == "users_timeouts"))
async def search_users_by_timeout_count(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Show users with timeout counts"""
    total_users = await UserRepository.get_users_by_timeout_count_total(1)
    if total_users == 0:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back",
                          callback_data=AdminMenuCallback.create(level=0, action="order_management"))
        await callback.message.edit_text(
            text="No users with timeouts found.",
            reply_markup=kb_builder.as_markup()
        )
        return

    page = callback_data.page
    users = await UserRepository.get_users_by_timeout_count(1, page)

    message_text = f"⏰ Users with Timeouts ({total_users} total):\n\n"
    for user in users:
        user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
        last_timeout = user.last_timeout_at.strftime('%Y-%m-%d %H:%M') if user.last_timeout_at else "N/A"
        message_text += f"{user_info} - {user.timeout_count} timeouts (Last: {last_timeout})\n"

    kb_builder = InlineKeyboardBuilder()
    back_button = AdminMenuCallback.create(level=0, action="order_management").get_back_button(0)
    kb_builder = await add_pagination_buttons(kb_builder, callback_data,
                                              UserRepository.get_users_by_timeout_count_max_page(1),
                                              back_button)

    await callback.message.edit_text(
        text=message_text,
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminMenuCallback.filter(F.action == "manual_cleanup"))
async def run_manual_cleanup(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Run manual cleanup of expired orders"""
    from services.background_tasks import BackgroundTaskService
    
    # Show processing message
    await callback.message.edit_text("🧹 Running cleanup... Please wait.")
    
    try:
        results = await BackgroundTaskService.run_single_cleanup()
        
        message_text = f"""🧹 Cleanup Results:

✅ Expired orders processed: {results['expired_orders']}
✅ Reservations cleaned: {results['cleaned_reservations']}"""
        
        if results['errors']:
            message_text += f"\n\n❌ Errors ({len(results['errors'])}):\n"
            for error in results['errors'][:5]:  # Show max 5 errors
                message_text += f"• {error}\n"
            if len(results['errors']) > 5:
                message_text += f"• ... and {len(results['errors']) - 5} more"
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminMenuCallback.create(level=0, action="order_management"))
        
        await callback.message.edit_text(
            text=message_text,  
            reply_markup=kb_builder.as_markup()
        )
        
    except Exception as e:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminMenuCallback.create(level=0, action="order_management"))
        
        await callback.message.edit_text(
            text=f"❌ Cleanup failed: {str(e)}",
            reply_markup=kb_builder.as_markup()
        )


@router.callback_query(AdminMenuCallback.filter(F.action == "access_private_key"))
async def access_private_key(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Securely access private key for paid order - ADMIN ONLY"""
    order_id = int(callback_data.args_to_action)
    admin_id = callback.from_user.id
    
    try:
        # Get order with decrypted private key (this logs the access)
        order_with_key = await OrderRepository.get_with_private_key(order_id, admin_id)
        
        if not order_with_key:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(text="◀️ Back", 
                              callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order_id))
            
            await callback.message.edit_text(
                text="❌ Order not found or private key unavailable.",
                reply_markup=kb_builder.as_markup()
            )
            return
        
        if order_with_key.status != "paid":
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(text="◀️ Back", 
                              callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order_id))
            
            await callback.message.edit_text(
                text="❌ Private key access only available for paid orders.",
                reply_markup=kb_builder.as_markup()
            )
            return
        
        # Security warning message with private key
        warning_text = f"""🔐 PRIVATE KEY ACCESS - CONFIDENTIAL

⚠️ SECURITY WARNING:
• This private key grants full control over the payment address
• Access is logged and audited
• Delete this message after use
• Never share or transmit this key insecurely

Order #{order_id}
Payment Address: {order_with_key.payment_address}
Private Key: `{order_with_key.private_key}`

Currency: {order_with_key.currency}
Amount: {order_with_key.total_amount}"""
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="🗑️ Delete This Message", 
                          callback_data=AdminMenuCallback.create(level=0, action="delete_key_message"))
        kb_builder.button(text="◀️ Back to Order", 
                          callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order_id))
        kb_builder.adjust(1)
        
        await callback.message.edit_text(
            text=warning_text,
            reply_markup=kb_builder.as_markup(),
            parse_mode="Markdown"
        )
        
        # Log the security event
        import logging
        security_logger = logging.getLogger('security')
        security_logger.critical(f"PRIVATE_KEY_ACCESS: Admin {admin_id} accessed private key for order {order_id} at {callback.message.date}")
        
    except Exception as e:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminMenuCallback.create(level=0, action="view_order", args_to_action=order_id))
        
        await callback.message.edit_text(
            text=f"❌ Error accessing private key: {str(e)}",
            reply_markup=kb_builder.as_markup()
        )


@router.callback_query(AdminMenuCallback.filter(F.action == "delete_key_message"))
async def delete_private_key_message(callback: CallbackQuery, callback_data: AdminMenuCallback):
    """Delete the private key message for security"""
    try:
        await callback.message.delete()
        
        # Send a temporary confirmation that gets deleted
        temp_message = await callback.message.answer("🗑️ Private key message deleted for security.")
        
        import asyncio
        # Delete the confirmation after 3 seconds
        await asyncio.sleep(3)
        await temp_message.delete()
        
    except Exception as e:
        # If deletion fails, edit the message to remove sensitive content
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back to Orders", 
                          callback_data=AdminMenuCallback.create(level=0, action="orders_ready_shipment", page=0))
        
        await callback.message.edit_text(
            text="🗑️ Private key message cleared for security.",
            reply_markup=kb_builder.as_markup()
        )