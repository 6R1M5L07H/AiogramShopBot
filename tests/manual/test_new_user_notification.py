#!/usr/bin/env python3
"""
Manual test script for admin new user notification.

Usage:
    python tests/manual/test_new_user_notification.py <telegram_id> [--force]

This script deletes a user from the database (including all related data),
so they can re-register and trigger the new user notification.

WARNING: This deletes ALL user data including orders, buys, and deposits!
         Only use with test accounts that have no real transaction history.

Example:
    python tests/manual/test_new_user_notification.py 123456789
    python tests/manual/test_new_user_notification.py 123456789 --force  # Skip confirmation
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from db import get_db_session, session_commit
from repositories.user import UserRepository
from repositories.cart import CartRepository
from repositories.user_strike import UserStrikeRepository
from repositories.order import OrderRepository
from repositories.buy import BuyRepository
from repositories.deposit import DepositRepository
from models.user import UserDTO
import config


async def check_user_data(user_id: int, session):
    """Check if user has any transaction history."""
    # Check orders
    orders = await OrderRepository.get_by_user_id(user_id, session)

    # Check buys
    buys = await BuyRepository.get_by_buyer_id(user_id, session)

    # Check deposits
    deposits = await DepositRepository.get_by_user_id(user_id, session)

    # Check strikes
    strikes = await UserStrikeRepository.get_by_user_id(user_id, session)

    return {
        'orders': len(orders) if orders else 0,
        'buys': len(buys) if buys else 0,
        'deposits': len(deposits) if deposits else 0,
        'strikes': len(strikes) if strikes else 0
    }


async def delete_user_completely(user_id: int, telegram_id: int, session):
    """Delete user and ALL related data."""
    print(f"\n🗑️  Deleting ALL data for user ID {user_id} (Telegram: {telegram_id})...")

    # Delete orders (including order items via CASCADE)
    orders = await OrderRepository.get_by_user_id(user_id, session)
    for order in orders:
        await OrderRepository.delete(order.id, session)
    print(f"   ✅ {len(orders)} orders deleted")

    # Delete buys
    buys = await BuyRepository.get_by_buyer_id(user_id, session)
    for buy in buys:
        await BuyRepository.delete(buy.id, session)
    print(f"   ✅ {len(buys)} buys deleted")

    # Delete deposits
    deposits = await DepositRepository.get_by_user_id(user_id, session)
    for deposit in deposits:
        await DepositRepository.delete(deposit.id, session)
    print(f"   ✅ {len(deposits)} deposits deleted")

    # Delete strikes
    strikes = await UserStrikeRepository.get_by_user_id(user_id, session)
    for strike in strikes:
        await UserStrikeRepository.delete(strike.id, session)
    print(f"   ✅ {len(strikes)} strikes deleted")

    # Delete cart
    await CartRepository.delete_by_user_id(user_id, session)
    print(f"   ✅ Cart deleted")

    # Delete user (payments have CASCADE, will be auto-deleted)
    await UserRepository.delete(user_id, session)
    print(f"   ✅ User deleted")

    # Commit all changes
    await session_commit(session)


async def delete_user_for_testing(telegram_id: int, force: bool = False):
    """
    Delete a user and all related data for testing new user registration.

    Args:
        telegram_id: Telegram user ID to delete
        force: Skip confirmation prompt
    """
    # SAFETY CHECK: Prevent deletion of admin accounts
    if telegram_id in config.ADMIN_ID_LIST:
        print(f"\n🛑 ADMIN PROTECTION ACTIVATED!")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"❌ Cannot delete admin account!")
        print(f"\nTelegram ID {telegram_id} is in ADMIN_ID_LIST (.env)")
        print(f"Admin accounts are protected from deletion.")
        print(f"\n💡 Solution: Use a test account that is NOT an admin.")
        return False

    async with get_db_session() as session:
        # Get user by telegram_id
        user = await UserRepository.get_by_tgid(telegram_id, session)

        if not user:
            print(f"❌ User with Telegram ID {telegram_id} not found in database.")
            print(f"\n✅ Good news: User can register and trigger notification!")
            return True

        print(f"\n🔍 Found user:")
        print(f"   Username: {user.telegram_username or 'No username'}")
        print(f"   Telegram ID: {telegram_id}")
        print(f"   Internal ID: {user.id}")
        print(f"   Wallet Balance: €{user.top_up_amount:.2f}")
        print(f"   Strikes: {user.strike_count}")

        # Check transaction history
        data_summary = await check_user_data(user.id, session)

        print(f"\n📊 Transaction History:")
        print(f"   Orders: {data_summary['orders']}")
        print(f"   Buys: {data_summary['buys']}")
        print(f"   Deposits: {data_summary['deposits']}")
        print(f"   Strikes: {data_summary['strikes']}")

        total_records = sum(data_summary.values())

        if total_records > 0 and not force:
            print(f"\n⚠️  WARNING: User has {total_records} database records!")
            print(f"⚠️  This will delete ALL user data including transaction history!")
            print(f"\n❓ Are you sure you want to delete this user? (yes/no): ", end='')

            confirm = input().strip().lower()
            if confirm not in ['yes', 'y']:
                print(f"\n❌ Deletion cancelled.")
                return False

        # Delete user and all data
        await delete_user_completely(user.id, telegram_id, session)

        print(f"\n✅ User with Telegram ID {telegram_id} successfully deleted!")
        print(f"\n📱 Test Instructions:")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"1. Make sure bot is running with NOTIFY_ADMIN_NEW_USER=true in .env")
        print(f"2. Open Telegram with account {telegram_id}")
        print(f"3. Send /start or interact with the bot")
        print(f"4. Check admin chat for new user registration notification")
        print(f"\n✨ User will be automatically re-created and admins notified!")

        return True


def main():
    if len(sys.argv) < 2:
        print("❌ Error: Telegram ID required")
        print(f"\nUsage: python {sys.argv[0]} <telegram_id> [--force]")
        print(f"Example: python {sys.argv[0]} 123456789")
        print(f"         python {sys.argv[0]} 123456789 --force  # Skip confirmation")
        sys.exit(1)

    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Error: '{sys.argv[1]}' is not a valid Telegram ID")
        print("Telegram ID must be a number (e.g., 123456789)")
        sys.exit(1)

    force = '--force' in sys.argv

    print(f"🧪 Test: New User Notification")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Target Telegram ID: {telegram_id}")
    print(f"Force mode: {'ON (no confirmation)' if force else 'OFF'}")

    # Run deletion
    success = asyncio.run(delete_user_for_testing(telegram_id, force))

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()