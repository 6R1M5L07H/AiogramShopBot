#!/usr/bin/env python3
"""
Unban Admin Script

Removes ban and resets strike count for admin user.
Useful for testing the strike system repeatedly.

Usage:
    python tests/strike-system/unban_admin.py --telegram-id <YOUR_TELEGRAM_ID>
    python tests/strike-system/unban_admin.py --telegram-id 123456789 --reset-strikes

Options:
    --telegram-id: Telegram ID of admin to unban (required)
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
from db import get_db_session
from repositories.user import UserRepository
from repositories.user_strike import UserStrikeRepository
from models.user import UserDTO


async def unban_admin(telegram_id: int, reset_strikes: bool = False, keep_records: bool = False):
    """
    Unbans an admin user and optionally resets their strikes.

    Args:
        telegram_id: Telegram ID of admin to unban
        reset_strikes: Whether to reset strike count to 0
        keep_records: Whether to keep UserStrike records in DB
    """
    async with get_db_session() as session:
        # Get user
        user = await UserRepository.get_by_tgid(telegram_id, session)

        if not user:
            print(f"❌ User with Telegram ID {telegram_id} not found in database")
            return False

        print(f"\n📋 Current Status:")
        print(f"   Telegram ID: {user.telegram_id}")
        print(f"   Username: @{user.telegram_username or 'N/A'}")
        print(f"   Banned: {'Yes' if user.is_blocked else 'No'}")
        print(f"   Strike Count: {user.strike_count}")

        if user.is_blocked:
            print(f"   Banned At: {user.blocked_at}")
            print(f"   Ban Reason: {user.blocked_reason}")

        # Get strike records
        strikes = await UserStrikeRepository.get_by_user_id(user.id, session)
        print(f"   Strike Records in DB: {len(strikes)}")

        if not user.is_blocked and user.strike_count == 0:
            print("\n✅ User is not banned and has no strikes. Nothing to do.")
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
            changes_made.append(f"Reset strike count to 0")

        if changes_made:
            await UserRepository.update(user, session)
            await session.commit()

        # Delete strike records if requested
        if not keep_records and len(strikes) > 0:
            # Note: This requires a delete method in UserStrikeRepository
            # For now, we'll just report it
            changes_made.append(f"NOTE: {len(strikes)} strike records still in DB (manual deletion needed)")

        print(f"\n✅ Changes Applied:")
        for change in changes_made:
            print(f"   • {change}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Unban admin user and optionally reset strikes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Unban admin but keep strike count
  python tests/strike-system/unban_admin.py --telegram-id 123456789

  # Unban admin and reset strikes to 0
  python tests/strike-system/unban_admin.py --telegram-id 123456789 --reset-strikes

  # Reset strikes but keep strike records in DB
  python tests/strike-system/unban_admin.py --telegram-id 123456789 --reset-strikes --keep-strike-records
        """
    )

    parser.add_argument("--telegram-id", type=int, required=True,
                        help="Telegram ID of admin to unban")
    parser.add_argument("--reset-strikes", action="store_true",
                        help="Reset strike count to 0")
    parser.add_argument("--keep-strike-records", action="store_true",
                        help="Keep UserStrike records in database")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Unban Admin Script")
    print(f"{'='*60}")

    success = asyncio.run(unban_admin(
        telegram_id=args.telegram_id,
        reset_strikes=args.reset_strikes,
        keep_records=args.keep_strike_records
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
