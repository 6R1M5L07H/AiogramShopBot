#!/usr/bin/env python3
"""
Unban Admin Script

Removes ban and resets strike count for admin users.
By default, unbans ALL admins from ADMIN_ID_LIST in .env.
Useful for testing the strike system repeatedly.

Usage:
    # Unban ALL admins from ADMIN_ID_LIST
    python tests/strike-system/unban_admin.py

    # Unban specific admin only
    python tests/strike-system/unban_admin.py --telegram-id 123456789

    # Unban ALL admins and reset their strikes
    python tests/strike-system/unban_admin.py --reset-strikes

Options:
    --telegram-id: Telegram ID of specific admin to unban (optional, default: all admins)
    --reset-strikes: Also reset strike count to 0 (optional)
    --keep-strike-records: Keep UserStrike records in DB (default: delete them)
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment to avoid webhook startup
os.environ["RUNTIME_ENVIRONMENT"] = "TEST"

import asyncio
from datetime import datetime

# Import all models to ensure SQLAlchemy relationships work
from models.user import User, UserDTO
from models.user_strike import UserStrike
from models.order import Order
from models.shipping_address import ShippingAddress
from models.item import Item
from models.category import Category
from models.subcategory import Subcategory

from db import get_db_session
from repositories.user import UserRepository
from repositories.user_strike import UserStrikeRepository
import config


async def unban_single_admin(telegram_id: int, reset_strikes: bool = False, keep_records: bool = False):
    """
    Unbans a single admin user and optionally resets their strikes.

    Args:
        telegram_id: Telegram ID of admin to unban
        reset_strikes: Whether to reset strike count to 0
        keep_records: Whether to keep UserStrike records in DB

    Returns:
        bool: True if successful, False if user not found
    """
    async with get_db_session() as session:
        # Get user
        user = await UserRepository.get_by_tgid(telegram_id, session)

        if not user:
            print(f"❌ User with Telegram ID {telegram_id} not found in database")
            return False

        print(f"\n📋 User: {telegram_id} (@{user.telegram_username or 'N/A'})")
        print(f"   Banned: {'Yes' if user.is_blocked else 'No'}")
        print(f"   Strike Count: {user.strike_count}")

        # Get strike records
        strikes = await UserStrikeRepository.get_by_user_id(user.id, session)
        print(f"   Strike Records: {len(strikes)}")

        if not user.is_blocked and user.strike_count == 0:
            print("   ✅ Already clean (no ban, no strikes)")
            return True

        # Apply changes
        changes_made = []

        if user.is_blocked:
            user.is_blocked = False
            user.blocked_at = None
            user.blocked_reason = None
            changes_made.append("Removed ban")

        if reset_strikes and user.strike_count > 0:
            user.strike_count = 0
            changes_made.append(f"Reset strikes")

        if changes_made:
            await UserRepository.update(user, session)
            await session.commit()
            print(f"   ✅ {', '.join(changes_made)}")
        else:
            print(f"   ℹ️  No changes needed")

        return True


async def unban_all_admins(reset_strikes: bool = False, keep_records: bool = False):
    """
    Unbans all admins from ADMIN_ID_LIST.

    Args:
        reset_strikes: Whether to reset strike count to 0
        keep_records: Whether to keep UserStrike records in DB

    Returns:
        int: Number of admins processed
    """
    admin_ids = config.ADMIN_ID_LIST

    if not admin_ids:
        print("❌ No admins found in ADMIN_ID_LIST")
        return 0

    print(f"📋 Processing {len(admin_ids)} admin(s) from ADMIN_ID_LIST...")

    success_count = 0
    for admin_id in admin_ids:
        success = await unban_single_admin(admin_id, reset_strikes, keep_records)
        if success:
            success_count += 1

    return success_count


def main():
    parser = argparse.ArgumentParser(
        description="Unban admin users and optionally reset strikes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Unban ALL admins from ADMIN_ID_LIST
  python tests/strike-system/unban_admin.py

  # Unban ALL admins and reset strikes
  python tests/strike-system/unban_admin.py --reset-strikes

  # Unban specific admin only
  python tests/strike-system/unban_admin.py --telegram-id 123456789

  # Unban specific admin and reset strikes
  python tests/strike-system/unban_admin.py --telegram-id 123456789 --reset-strikes
        """
    )

    parser.add_argument("--telegram-id", type=int, required=False,
                        help="Telegram ID of specific admin to unban (default: all admins from ADMIN_ID_LIST)")
    parser.add_argument("--reset-strikes", action="store_true",
                        help="Reset strike count to 0")
    parser.add_argument("--keep-strike-records", action="store_true",
                        help="Keep UserStrike records in database")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Unban Admin Script")
    print(f"{'='*60}")

    if args.telegram_id:
        # Unban specific admin
        print(f"\n🎯 Mode: Single Admin ({args.telegram_id})")
        success = asyncio.run(unban_single_admin(
            telegram_id=args.telegram_id,
            reset_strikes=args.reset_strikes,
            keep_records=args.keep_strike_records
        ))
        result = success
    else:
        # Unban all admins from ADMIN_ID_LIST
        print(f"\n🎯 Mode: All Admins from ADMIN_ID_LIST")
        count = asyncio.run(unban_all_admins(
            reset_strikes=args.reset_strikes,
            keep_records=args.keep_strike_records
        ))
        print(f"\n✅ Processed {count} admin(s)")
        result = count > 0

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
