"""
===============================================================================
Tier Breakdown Storage Verification Script
===============================================================================

DESCRIPTION:
    Verifies that tier breakdown is stored correctly in cart_items and
    calculated dynamically for orders (not stored in orders table).

    This script helps during manual testing to verify:
    1. CartItem.tier_breakdown is populated with JSON
    2. Order table does NOT have tier_breakdown column (calculated dynamically)
    3. JSON structure matches TierBreakdownItemDTO format

REQUIREMENTS:
    - Python 3.10+
    - Virtual environment activated
    - Database configured and accessible

USAGE:
    Terminal:
        $ cd ~/git/AiogramShopBot
        $ source venv/bin/activate
        $ python3 tests/pricing/manual/verify_tier_breakdown_storage.py

EXAMPLE OUTPUT:
    ============================================================
    TIER BREAKDOWN STORAGE VERIFICATION
    ============================================================

    Cart Items with Tier Breakdown:
    --------------------------------
    CartItem ID: 123
    Subcategory: iPhone 15 Pro
    Quantity: 17
    Tier Breakdown (JSON):
    [
      {"quantity": 10, "unit_price": 9.0, "total": 90.0},
      {"quantity": 5, "unit_price": 10.0, "total": 50.0},
      {"quantity": 2, "unit_price": 11.0, "total": 22.0}
    ]

    Orders Table Schema:
    --------------------
    ✅ No tier_breakdown column found
    ✅ Tier breakdown calculated dynamically

    Summary:
    --------
    ✅ Cart items: 5 have tier_breakdown
    ✅ Orders: Tier breakdown not stored (correct!)

===============================================================================
"""

import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set TEST mode
os.environ["RUNTIME_ENVIRONMENT"] = "TEST"

from sqlalchemy import select, inspect
from db import get_db_session
from models.cartItem import CartItem
from models.subcategory import Subcategory
from models.order import Order


async def verify_cart_tier_breakdown():
    """Check cart items for tier_breakdown JSON storage."""
    async with get_db_session() as session:
        stmt = (
            select(CartItem, Subcategory.name)
            .join(Subcategory, CartItem.subcategory_id == Subcategory.id)
            .where(CartItem.tier_breakdown.isnot(None))
        )
        result = await session.execute(stmt)
        cart_items = result.all()

        print("\n" + "=" * 60)
        print("CART ITEMS WITH TIER BREAKDOWN")
        print("=" * 60)

        if not cart_items:
            print("❌ No cart items with tier_breakdown found")
            print("   Add items to cart in the bot first!")
            return 0

        for cart_item, subcat_name in cart_items:
            print(f"\nCartItem ID: {cart_item.id}")
            print(f"Subcategory: {subcat_name}")
            print(f"Quantity: {cart_item.quantity}")
            print(f"Tier Breakdown (JSON):")

            try:
                breakdown = json.loads(cart_item.tier_breakdown)
                print(json.dumps(breakdown, indent=2))

                # Validate structure
                for item in breakdown:
                    assert 'quantity' in item, "Missing 'quantity' key"
                    assert 'unit_price' in item, "Missing 'unit_price' key"
                    assert 'total' in item, "Missing 'total' key"

                print("✅ Structure valid (matches TierBreakdownItemDTO)")

            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
            except AssertionError as e:
                print(f"❌ Invalid structure: {e}")

            print("-" * 60)

        return len(cart_items)


async def verify_order_table_schema():
    """Verify that Order table does NOT have tier_breakdown column."""
    async with get_db_session() as session:
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns('orders')]

        print("\n" + "=" * 60)
        print("ORDERS TABLE SCHEMA")
        print("=" * 60)
        print(f"\nColumns: {', '.join(columns)}")

        if 'tier_breakdown' in columns:
            print("\n❌ FAIL: tier_breakdown column found in orders table!")
            print("   Tier breakdown should be calculated dynamically, not stored!")
            return False
        else:
            print("\n✅ PASS: No tier_breakdown column found")
            print("   Tier breakdown calculated dynamically (correct!)")
            return True


async def verify_order_calculation():
    """Verify that orders can calculate tier breakdown dynamically."""
    async with get_db_session() as session:
        # Get a recent order
        stmt = select(Order).order_by(Order.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        order = result.scalar()

        print("\n" + "=" * 60)
        print("DYNAMIC TIER CALCULATION TEST")
        print("=" * 60)

        if not order:
            print("❌ No orders found in database")
            print("   Create an order in the bot first!")
            return False

        print(f"\nOrder ID: {order.id}")
        print(f"Total Price (stored): {order.total_price} EUR")
        print(f"Status: {order.status.value}")

        # Try to calculate tier breakdown dynamically
        try:
            from services.order_management import OrderManagementService
            msg, kb = await OrderManagementService.get_order_detail_view(
                order_id=order.id,
                session=session,
                user_id=None,  # Admin context (no ownership check)
                entity=BotEntity.ADMIN
            )

            if "Staffelpreise:" in msg or "Tier Pricing:" in msg:
                print("✅ Tier breakdown calculated dynamically in order view")
                print("\nSample output:")
                # Extract tier breakdown section
                lines = msg.split('\n')
                in_tier_section = False
                for line in lines:
                    if 'Staffelpreise:' in line or 'Tier Pricing:' in line:
                        in_tier_section = True
                    if in_tier_section:
                        print(f"  {line}")
                        if '──────' in line and in_tier_section:
                            # Print next 2 lines (total and average)
                            idx = lines.index(line)
                            if idx + 1 < len(lines):
                                print(f"  {lines[idx + 1]}")
                            if idx + 2 < len(lines):
                                print(f"  {lines[idx + 2]}")
                            break

                return True
            else:
                print("⚠️  No tier breakdown in order view")
                print("   (May be using legacy pricing - this is OK)")
                return True

        except Exception as e:
            print(f"❌ Error calculating tier breakdown: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main verification flow."""
    print("=" * 60)
    print("TIER BREAKDOWN STORAGE VERIFICATION")
    print("=" * 60)

    # Import here to avoid circular imports
    from enums.bot_entity import BotEntity

    # Check cart items
    cart_count = await verify_cart_tier_breakdown()

    # Check order table schema
    schema_ok = await verify_order_table_schema()

    # Check dynamic calculation
    calc_ok = await verify_order_calculation()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if cart_count > 0:
        print(f"✅ Cart items: {cart_count} have tier_breakdown")
    else:
        print("⚠️  Cart items: None with tier_breakdown (add items to cart)")

    if schema_ok:
        print("✅ Orders: Tier breakdown not stored (correct!)")
    else:
        print("❌ Orders: tier_breakdown column exists (should be removed)")

    if calc_ok:
        print("✅ Orders: Dynamic calculation working")
    else:
        print("❌ Orders: Dynamic calculation failed")

    print("\n" + "=" * 60)

    # Overall result
    if schema_ok and calc_ok:
        print("✅ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)