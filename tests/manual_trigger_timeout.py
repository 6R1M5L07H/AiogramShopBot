"""
Manual Timeout Trigger - For Testing Mixed Order Refunds

Usage:
    python tests/manual_trigger_timeout.py

This will:
1. Find the most recent PENDING order
2. Manually trigger the timeout cancellation
3. Show refund breakdown in logs
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s'
)

from db import get_db_session
from repositories.order import OrderRepository
from services.order import OrderService
from enums.order_cancel_reason import OrderCancelReason
from enums.order_status import OrderStatus


async def main():
    """Manually trigger timeout for most recent pending order."""
    print("=" * 80)
    print("MANUAL TIMEOUT TRIGGER - Mixed Order Refund Test")
    print("=" * 80)

    async with get_db_session() as session:
        # Find most recent pending order
        pending_orders = await OrderRepository.get_expired_orders(session)

        if not pending_orders:
            print("\n❌ No expired orders found.")
            print("\nSearching for ANY pending orders (even if not expired)...")

            # Get ANY pending order
            from sqlalchemy import select
            from models.order import Order
            from db import session_execute

            stmt = select(Order).where(
                Order.status.in_([
                    OrderStatus.PENDING_PAYMENT,
                    OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
                    OrderStatus.PENDING_PAYMENT_PARTIAL
                ])
            ).order_by(Order.created_at.desc()).limit(1)

            result = await session_execute(stmt, session)
            order = result.scalar_one_or_none()

            if not order:
                print("❌ No pending orders at all!")
                return

            print(f"\n✅ Found pending order: {order.id}")
            print(f"   Status: {order.status.value}")
            print(f"   Total: {order.total_price}€")
            print(f"   Created: {order.created_at}")
            print(f"   Expires: {order.expires_at}")
            print(f"\n⚠️  Order is NOT expired yet, but proceeding with manual timeout...")
        else:
            order = pending_orders[0]
            print(f"\n✅ Found expired order: {order.id}")
            print(f"   Status: {order.status.value}")
            print(f"   Total: {order.total_price}€")
            print(f"   Expired at: {order.expires_at}")

        # Get items to show what's in the order
        from repositories.item import ItemRepository
        items = await ItemRepository.get_by_order_id(order.id, session)

        print(f"\n📦 Order contains {len(items)} items:")
        for item in items:
            item_type = "Physical" if item.is_physical else "Digital"
            print(f"   - {item_type}: {item.price}€")

        # Ask for confirmation
        print("\n" + "=" * 80)
        response = input("Trigger TIMEOUT cancellation for this order? [y/N]: ")

        if response.lower() != 'y':
            print("❌ Aborted")
            return

        print("\n🔄 Triggering timeout cancellation...")
        print("=" * 80)

        # Trigger the cancellation
        within_grace_period, message = await OrderService.cancel_order(
            order_id=order.id,
            reason=OrderCancelReason.TIMEOUT,
            session=session
        )

        await session.commit()

        print("\n" + "=" * 80)
        print("✅ TIMEOUT TRIGGERED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nOrder {order.id} has been cancelled.")
        print(f"Message: {message}")
        print(f"Within grace period: {within_grace_period}")

        print("\n📋 Check logs for refund breakdown:")
        print("   Look for: 'digital_items_delivered'")
        print("   Look for: 'refundable_base'")
        print("   Look for: 'digital_refundable_amount'")


if __name__ == "__main__":
    asyncio.run(main())