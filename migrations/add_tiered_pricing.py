#!/usr/bin/env python3
"""
Migration: Add Tiered Pricing Support
Date: 2025-11-06

This migration:
1. Creates price_tiers table
2. Adds tier_breakdown column to cart_items
3. Migrates existing items to single-tier system (legacy price → tier)

Usage:
    python migrations/add_tiered_pricing.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from db import get_db_session, session_commit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_migration():
    """Execute the tiered pricing migration."""
    logger.info("=" * 60)
    logger.info("TIERED PRICING MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Create price_tiers table
            logger.info("Step 1: Creating price_tiers table...")
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS price_tiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
                    unit_price REAL NOT NULL CHECK (unit_price > 0),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                )
            """))
            logger.info("✅ price_tiers table created")

            # Step 2: Create indexes
            logger.info("Step 2: Creating indexes...")
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_price_tiers_item_id
                ON price_tiers(item_id)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_price_tiers_min_quantity
                ON price_tiers(item_id, min_quantity)
            """))
            logger.info("✅ Indexes created")

            # Step 3: Add tier_breakdown column to cart_items
            logger.info("Step 3: Extending cart_items table...")
            try:
                await session.execute(text("""
                    ALTER TABLE cart_items ADD COLUMN tier_breakdown TEXT NULL
                """))
                logger.info("✅ tier_breakdown column added")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  tier_breakdown column already exists, skipping")
                else:
                    raise

            # Step 4: Migrate existing items
            logger.info("Step 4: Migrating existing items to tiered pricing...")

            # Get count of items to migrate
            result = await session.execute(text("""
                SELECT COUNT(*) FROM items
                WHERE price IS NOT NULL AND price > 0
            """))
            item_count = result.scalar()
            logger.info(f"Found {item_count} items to migrate")

            if item_count > 0:
                # Insert single tier for each item (legacy price → tier)
                await session.execute(text("""
                    INSERT INTO price_tiers (item_id, min_quantity, unit_price)
                    SELECT id, 1, price
                    FROM items
                    WHERE price IS NOT NULL AND price > 0
                    AND id NOT IN (SELECT DISTINCT item_id FROM price_tiers)
                """))
                logger.info(f"✅ Migrated {item_count} items to single-tier system")
            else:
                logger.info("⚠️  No items to migrate")

            # Step 5: Commit transaction
            await session_commit(session)
            logger.info("✅ Transaction committed")

            # Step 6: Verification
            logger.info("")
            logger.info("=" * 60)
            logger.info("VERIFICATION")
            logger.info("=" * 60)

            # Check items without tiers
            result = await session.execute(text("""
                SELECT COUNT(*) FROM items
                WHERE id NOT IN (SELECT DISTINCT item_id FROM price_tiers)
            """))
            items_without_tiers = result.scalar()

            if items_without_tiers == 0:
                logger.info(f"✅ All items have price tiers")
            else:
                logger.warning(f"⚠️  {items_without_tiers} items have no price tiers")

            # Show tier distribution
            result = await session.execute(text("""
                SELECT
                    COUNT(DISTINCT item_id) as items_with_tiers,
                    COUNT(*) as total_tiers
                FROM price_tiers
            """))
            row = result.fetchone()
            logger.info(f"📊 {row[0]} items with {row[1]} total tiers")

            # Show sample tiers
            logger.info("")
            logger.info("Sample price tiers:")
            result = await session.execute(text("""
                SELECT
                    pt.item_id,
                    i.description,
                    pt.min_quantity,
                    pt.unit_price
                FROM price_tiers pt
                JOIN items i ON i.id = pt.item_id
                ORDER BY pt.item_id, pt.min_quantity
                LIMIT 5
            """))

            for row in result:
                logger.info(f"  Item {row[0]} ({row[1]}): {row[2]}+ → €{row[3]:.2f}")

            logger.info("")
            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. Restart the bot to load new models")
            logger.info("2. Test with: python tests/pricing/test_basic_pricing.py")
            logger.info("3. Verify in bot: Select an item and check price display")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)