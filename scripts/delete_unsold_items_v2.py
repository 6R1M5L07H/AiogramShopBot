#!/usr/bin/env python3
"""
Script to reset all items to is_new=False

This is useful when you want to reset the "new items" flag for all items
in the database, for example after testing or when you want to manually
control which items are announced as restocked.

Usage:
    python scripts/reset_items_is_new.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db import get_session, session_commit
from repositories.item import ItemRepository


async def reset_is_new_flag():
    """Reset is_new flag to False for all items"""
    print("🔄 Resetting is_new flag for all items...")

    async with get_session() as session:
        # Get count before reset
        items_before = await ItemRepository.get_new(session)
        count_before = len(items_before)

        print(f"📊 Found {count_before} items with is_new=True")

        if count_before == 0:
            print("✅ No items to reset. All items already have is_new=False")
            return

        # Reset all items
        await ItemRepository.set_not_new(session)
        await session_commit(session)

        # Verify after reset
        items_after = await ItemRepository.get_new(session)
        count_after = len(items_after)

        print(f"✅ Reset complete! {count_before} items set to is_new=False")
        print(f"📊 Remaining items with is_new=True: {count_after}")

        if count_after > 0:
            print("⚠️  Warning: Some items still have is_new=True")
        else:
            print("✅ All items successfully reset!")


async def main():
    try:
        await reset_is_new_flag()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
