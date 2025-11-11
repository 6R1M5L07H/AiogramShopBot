#!/usr/bin/env python3
"""
Migration: Add Shipping Tiers Support
Date: 2025-11-10

This migration:
1. Creates shipping_tiers table for quantity-based shipping type selection
2. Migrates existing physical items to default "maxibrief" tier
3. Digital items (is_physical=False) get no shipping tiers (as expected)

Usage:
    python migrations/add_shipping_tiers.py
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
    """Execute the shipping tiers migration."""
    logger.info("=" * 60)
    logger.info("SHIPPING TIERS MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Create shipping_tiers table
            logger.info("Step 1: Creating shipping_tiers table...")
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS shipping_tiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subcategory_id INTEGER NOT NULL,
                    min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
                    max_quantity INTEGER NULL CHECK (max_quantity IS NULL OR max_quantity >= min_quantity),
                    shipping_type TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE CASCADE
                )
            """))
            logger.info("✅ shipping_tiers table created")

            # Step 2: Create indexes
            logger.info("Step 2: Creating indexes...")
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_shipping_tiers_subcategory_id
                ON shipping_tiers(subcategory_id)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_shipping_tiers_quantity_range
                ON shipping_tiers(subcategory_id, min_quantity, max_quantity)
            """))
            logger.info("✅ Indexes created")

            # Step 3: Migrate existing physical items
            logger.info("Step 3: Migrating existing physical items to default shipping tier...")

            # Get count of physical subcategories
            result = await session.execute(text("""
                SELECT COUNT(DISTINCT subcategory_id)
                FROM items
                WHERE is_physical = 1
            """))
            physical_subcategories_count = result.scalar()
            logger.info(f"Found {physical_subcategories_count} physical subcategories to migrate")

            if physical_subcategories_count > 0:
                # Insert default "maxibrief" tier for each physical subcategory
                # Only if subcategory doesn't already have shipping tiers
                # IMPORTANT: Only migrate subcategories that actually exist (avoid FK constraint errors)
                await session.execute(text("""
                    INSERT INTO shipping_tiers (subcategory_id, min_quantity, max_quantity, shipping_type)
                    SELECT DISTINCT i.subcategory_id, 1, NULL, 'maxibrief'
                    FROM items i
                    INNER JOIN subcategories s ON s.id = i.subcategory_id
                    WHERE i.is_physical = 1
                    AND i.subcategory_id NOT IN (SELECT DISTINCT subcategory_id FROM shipping_tiers)
                """))
                logger.info(f"✅ Migrated {physical_subcategories_count} physical subcategories to default 'maxibrief' tier")
                logger.info("⚠️  Note: Manual adjustment recommended for optimal shipping configuration")
            else:
                logger.info("⚠️  No physical subcategories to migrate")

            # Step 4: Commit transaction
            await session_commit(session)
            logger.info("✅ Transaction committed")

            # Step 5: Verification
            logger.info("")
            logger.info("=" * 60)
            logger.info("VERIFICATION")
            logger.info("=" * 60)

            # Check physical subcategories without tiers
            result = await session.execute(text("""
                SELECT COUNT(DISTINCT subcategory_id)
                FROM items
                WHERE is_physical = 1
                AND subcategory_id NOT IN (SELECT DISTINCT subcategory_id FROM shipping_tiers)
            """))
            physical_without_tiers = result.scalar()

            if physical_without_tiers == 0:
                logger.info(f"✅ All physical subcategories have shipping tiers")
            else:
                logger.warning(f"⚠️  {physical_without_tiers} physical subcategories have no shipping tiers")

            # Check digital items (should have NO tiers)
            result = await session.execute(text("""
                SELECT COUNT(DISTINCT subcategory_id)
                FROM items
                WHERE is_physical = 0
                AND subcategory_id IN (SELECT DISTINCT subcategory_id FROM shipping_tiers)
            """))
            digital_with_tiers = result.scalar()

            if digital_with_tiers == 0:
                logger.info(f"✅ No digital subcategories have shipping tiers (as expected)")
            else:
                logger.warning(f"⚠️  {digital_with_tiers} digital subcategories have shipping tiers (unexpected!)")

            # Show tier distribution
            result = await session.execute(text("""
                SELECT
                    COUNT(DISTINCT subcategory_id) as subcategories_with_tiers,
                    COUNT(*) as total_tiers
                FROM shipping_tiers
            """))
            row = result.fetchone()
            logger.info(f"📊 {row[0]} subcategories with {row[1]} total shipping tiers")

            # Show sample tiers with subcategory names
            logger.info("")
            logger.info("Sample shipping tiers:")
            result = await session.execute(text("""
                SELECT
                    st.subcategory_id,
                    s.name,
                    st.min_quantity,
                    st.max_quantity,
                    st.shipping_type
                FROM shipping_tiers st
                JOIN subcategories s ON s.id = st.subcategory_id
                ORDER BY st.subcategory_id, st.min_quantity
                LIMIT 10
            """))

            for row in result:
                max_qty = f"{row[3]}" if row[3] else "∞"
                logger.info(f"  Subcategory {row[0]} ({row[1]}): {row[2]}-{max_qty} → {row[4]}")

            logger.info("")
            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. Review default 'maxibrief' assignments in database")
            logger.info("2. Update shipping_tiers via JSON import or manual DB edit")
            logger.info("3. Restart the bot to load new models")
            logger.info("4. Test cart shipping calculation with physical items")
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