from datetime import datetime
from enums.bot_entity import BotEntity
from models.item import ItemDTO
from models.order import OrderDTO
from models.user import UserDTO
from utils.localizator import Localizator
import config


class MessageService:
    @staticmethod
    def create_message_with_bought_items(items: list[ItemDTO]):
        message = "<b>"
        for count, item in enumerate(items, start=1):
            private_data = item.private_data
            message += Localizator.get_text(BotEntity.USER, "purchased_item").format(count=count,
                                                                                     private_data=private_data)
        message += "</b>\n"
        return message
    
    @staticmethod
    def create_order_payment_instructions(order: OrderDTO) -> str:
        """Create payment instructions message for order"""
        timeout_minutes = getattr(config, 'ORDER_TIMEOUT_MINUTES', 30)
        
        return Localizator.get_text(BotEntity.USER, "order_created_success").format(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency,
            address=order.payment_address,
            timeout_minutes=timeout_minutes
        )
    
    @staticmethod
    def create_order_status_message(order: OrderDTO) -> str:
        """Create order status message"""
        status_messages = {
            "created": "⏳ Awaiting Payment",
            "paid": "✅ Paid - Ready for Shipment", 
            "shipped": "📦 Shipped",
            "cancelled": "❌ Cancelled",
            "expired": "⏰ Expired"
        }
        
        status_text = status_messages.get(order.status, order.status.title())
        
        message = f"""📦 <b>Order #{order.id}</b>
        
<b>Status:</b> {status_text}
<b>Amount:</b> {order.total_amount} {order.currency}
<b>Created:</b> {order.created_at.strftime('%Y-%m-%d %H:%M')}"""
        
        if order.status == "created":
            time_remaining = (order.expires_at - datetime.now()).total_seconds()
            if time_remaining > 0:
                minutes_remaining = int(time_remaining / 60)
                message += f"\n<b>Time remaining:</b> {minutes_remaining} minutes"
                message += f"\n<b>Payment Address:</b> <code>{order.payment_address}</code>"
        
        if order.paid_at:
            message += f"\n<b>Paid:</b> {order.paid_at.strftime('%Y-%m-%d %H:%M')}"
        
        if order.shipped_at:
            message += f"\n<b>Shipped:</b> {order.shipped_at.strftime('%Y-%m-%d %H:%M')}"
        
        return message
    
    @staticmethod
    def create_admin_order_summary(order: OrderDTO, user: UserDTO) -> str:
        """Create admin order summary message"""
        user_info = f"@{user.telegram_username}" if user.telegram_username else f"ID: {user.telegram_id}"
        
        message = f"""📦 <b>Order #{order.id}</b>
        
<b>User:</b> {user_info}
<b>Status:</b> {order.status.upper()}
<b>Amount:</b> {order.total_amount} {order.currency}
<b>Payment Address:</b> <code>{order.payment_address}</code>
<b>Created:</b> {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        if order.paid_at:
            message += f"\n<b>Paid:</b> {order.paid_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
        if order.shipped_at:
            message += f"\n<b>Shipped:</b> {order.shipped_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
