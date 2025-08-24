from aiogram import types, Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks import AdminCallback
from enums.bot_entity import BotEntity
from handlers.admin.constants import ELEMENTS_ON_PAGE
from repositories.order import OrderRepository
from repositories.user import UserRepository
from services.order import OrderService
from utils.localizator import Localizator

router = Router()


@router.callback_query(AdminCallback.filter(F.action == "order_management"))
async def show_order_management_menu(callback: CallbackQuery, callback_data: AdminCallback):
    """Show order management main menu"""
    kb_builder = InlineKeyboardBuilder()
    
    # Orders ready for shipment
    kb_builder.button(text="📦 Orders Ready for Shipment", 
                      callback_data=AdminCallback.create("orders_ready_shipment", page=0))
    
    # Search users by timeout count
    kb_builder.button(text="⏰ Users with Timeouts", 
                      callback_data=AdminCallback.create("users_timeouts", page=0))
    
    # Manual cleanup orders
    kb_builder.button(text="🧹 Run Cleanup", 
                      callback_data=AdminCallback.create("manual_cleanup"))
    
    # Back to admin menu
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminCallback.create("admin_panel"))
    
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text="📦 Order Management\n\nSelect an option:",
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminCallback.filter(F.action == "orders_ready_shipment"))
async def show_orders_ready_for_shipment(callback: CallbackQuery, callback_data: AdminCallback):
    """Show orders that are ready for shipment"""
    orders = await OrderRepository.get_orders_ready_for_shipment()
    
    if not orders:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminCallback.create("order_management"))
        
        await callback.message.edit_text(
            text="No orders ready for shipment.",
            reply_markup=kb_builder.as_markup()
        )
        return
    
    kb_builder = InlineKeyboardBuilder()
    
    # Show orders with pagination
    page = callback_data.page or 0
    start_idx = page * ELEMENTS_ON_PAGE
    end_idx = start_idx + ELEMENTS_ON_PAGE
    
    page_orders = orders[start_idx:end_idx]
    
    for order in page_orders:
        user = await UserRepository.get_user_entity(order.user_id)
        user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
        
        kb_builder.button(
            text=f"Order #{order.id} - {user_info} - {order.total_amount} {order.currency}",
            callback_data=AdminCallback.create("view_order", order_id=order.id)
        )
    
    # Pagination
    total_pages = (len(orders) + ELEMENTS_ON_PAGE - 1) // ELEMENTS_ON_PAGE
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="◀️", 
                callback_data=AdminCallback.create("orders_ready_shipment", page=page-1)
            ))
        
        nav_buttons.append(types.InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}", 
            callback_data="noop"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="▶️", 
                callback_data=AdminCallback.create("orders_ready_shipment", page=page+1)
            ))
        
        kb_builder.row(*nav_buttons)
    
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminCallback.create("order_management"))
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text=f"📦 Orders Ready for Shipment ({len(orders)} total):",
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminCallback.filter(F.action == "view_order"))
async def view_order_details(callback: CallbackQuery, callback_data: AdminCallback):
    """View detailed order information"""
    order_id = callback_data.order_id
    order = await OrderRepository.get_by_id(order_id)
    
    if not order:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminCallback.create("orders_ready_shipment", page=0))
        
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
                          callback_data=AdminCallback.create("ship_order", order_id=order.id))
    
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminCallback.create("orders_ready_shipment", page=0))
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminCallback.filter(F.action == "ship_order"))
async def mark_order_as_shipped(callback: CallbackQuery, callback_data: AdminCallback):
    """Mark order as shipped"""
    order_id = callback_data.order_id
    
    try:
        await OrderService.ship_order(order_id)
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back to Orders", 
                          callback_data=AdminCallback.create("orders_ready_shipment", page=0))
        
        await callback.message.edit_text(
            text=f"✅ Order #{order_id} has been marked as shipped!\nUser has been notified.",
            reply_markup=kb_builder.as_markup()
        )
        
    except Exception as e:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminCallback.create("view_order", order_id=order_id))
        
        await callback.message.edit_text(
            text=f"❌ Error shipping order: {str(e)}",
            reply_markup=kb_builder.as_markup()
        )


@router.callback_query(AdminCallback.filter(F.action == "users_timeouts"))
async def search_users_by_timeout_count(callback: CallbackQuery, callback_data: AdminCallback):
    """Show users with timeout counts"""
    users = await UserRepository.get_users_by_timeout_count(1)  # Users with at least 1 timeout
    
    if not users:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminCallback.create("order_management"))
        
        await callback.message.edit_text(
            text="No users with timeouts found.",
            reply_markup=kb_builder.as_markup()
        )
        return
    
    # Show users with pagination
    page = callback_data.page or 0
    start_idx = page * ELEMENTS_ON_PAGE
    end_idx = start_idx + ELEMENTS_ON_PAGE
    
    page_users = users[start_idx:end_idx]
    
    message_text = f"⏰ Users with Timeouts ({len(users)} total):\n\n"
    
    for user in page_users:
        user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
        last_timeout = user.last_timeout_at.strftime('%Y-%m-%d %H:%M') if user.last_timeout_at else "N/A"
        message_text += f"{user_info} - {user.timeout_count} timeouts (Last: {last_timeout})\n"
    
    kb_builder = InlineKeyboardBuilder()
    
    # Pagination
    total_pages = (len(users) + ELEMENTS_ON_PAGE - 1) // ELEMENTS_ON_PAGE
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="◀️", 
                callback_data=AdminCallback.create("users_timeouts", page=page-1)
            ))
        
        nav_buttons.append(types.InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}", 
            callback_data="noop"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="▶️", 
                callback_data=AdminCallback.create("users_timeouts", page=page+1)
            ))
        
        kb_builder.row(*nav_buttons)
    
    kb_builder.button(text="◀️ Back", 
                      callback_data=AdminCallback.create("order_management"))
    kb_builder.adjust(1)
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(AdminCallback.filter(F.action == "manual_cleanup"))
async def run_manual_cleanup(callback: CallbackQuery, callback_data: AdminCallback):
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
                          callback_data=AdminCallback.create("order_management"))
        
        await callback.message.edit_text(
            text=message_text,  
            reply_markup=kb_builder.as_markup()
        )
        
    except Exception as e:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="◀️ Back", 
                          callback_data=AdminCallback.create("order_management"))
        
        await callback.message.edit_text(
            text=f"❌ Cleanup failed: {str(e)}",
            reply_markup=kb_builder.as_markup()
        )