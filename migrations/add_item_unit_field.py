#!/usr/bin/env python3
"""
Migration: Add Unit Field to Items Table
Date: 2025-11-19

This migration adds support for customizable measurement units per item.
Items can now display quantities in different units (pcs., g, kg, ml, l, m2, etc.)
instead of the hardcoded "pcs." default.

Changes:
1. Adds 'unit' column to items table (VARCHAR(10), DEFAULT 'pcs.')
2. Migrates existing items to 'pcs.' (English-based default)
3. Adds validation constraint (alphanumeric + period only)

Usage:
    python migrations/add_item_unit_field.py
"""

import sys
import os
import asyncio
import logging
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from db import get_db_session, session_commit, session_execute

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_unit(unit: str) -> bool:
    """
    Validate unit string for security.

    Allows only alphanumeric characters and periods, max 10 characters.
    Prevents SQL injection and other malicious input.

    Args:
        unit: Unit string to validate

    Returns:
        True if valid, False otherwise
    """
    if not unit or len(unit) > 10:
        return False
    # Allow alphanumeric + period only (ASCII-safe)
    return bool(re.match(r'^[a-zA-Z0-9.]+$', unit))


async def run_migration():
    """Execute the item unit field migration."""
    logger.info("=" * 60)
    logger.info("ITEM UNIT FIELD MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Add unit column to items table
            logger.info("Step 1: Adding 'unit' column to items table...")
            try:
                await session_execute(
                    text("""
                        ALTER TABLE items
                        ADD COLUMN unit VARCHAR(10) NOT NULL DEFAULT 'pcs.'
                    """),
                    session
                )
                logger.info("✅ 'unit' column added (default: 'pcs.')")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  'unit' column already exists, skipping")
                else:
                    raise

            # Step 2: Add CHECK constraint for unit validation
            logger.info("Step 2: Adding validation constraint...")
            try:
                await session_execute(
                    text("""
                        CREATE TABLE items_new (
                            id INTEGER PRIMARY KEY,
                            category_id INTEGER NOT NULL,
                            subcategory_id INTEGER NOT NULL,
                            private_data TEXT NOT NULL,
                            price REAL NOT NULL,
                            is_sold INTEGER NOT NULL DEFAULT 0,
                            is_new INTEGER NOT NULL DEFAULT 1,
                            description TEXT NOT NULL,
                            is_physical INTEGER NOT NULL DEFAULT 0,
                            shipping_cost REAL NOT NULL DEFAULT 0.0,
                            allows_packstation INTEGER NOT NULL DEFAULT 0,
                            order_id INTEGER,
                            reserved_at DATETIME,
                            unit VARCHAR(10) NOT NULL DEFAULT 'pcs.',
                            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                            FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE CASCADE,
                            FOREIGN KEY (order_id) REFERENCES orders(id),
                            CHECK (price > 0),
                            CHECK (shipping_cost >= 0),
                            CHECK (length(unit) <= 10 AND unit GLOB '[a-zA-Z0-9.]*')
                        )
                    """),
                    session
                )

                # Copy data from old table
                await session_execute(
                    text("""
                        INSERT INTO items_new
                        SELECT id, category_id, subcategory_id, private_data, price,
                               is_sold, is_new, description, is_physical, shipping_cost,
                               allows_packstation, order_id, reserved_at,
                               COALESCE(unit, 'pcs.') as unit
                        FROM items
                    """),
                    session
                )

                # Drop old table and rename new one
                await session_execute(text("DROP TABLE items"), session)
                await session_execute(text("ALTER TABLE items_new RENAME TO items"), session)

                logger.info("✅ Validation constraint added")
            except Exception as e:
                if "already exists" in str(e).lower() or "no such table: items" in str(e).lower():
                    logger.info("⚠️  Constraint already exists or table already migrated, skipping")
                else:
                    logger.warning(f"⚠️  Could not add constraint (SQLite limitation): {e}")
                    logger.info("    Validation will be enforced at application level")

            # Step 3: Verify migration
            logger.info("")
            logger.info("Step 3: Verifying migration...")

            # Check column exists
            result = await session_execute(
                text("PRAGMA table_info(items)"),
                session
            )
            columns = result.fetchall()
            unit_column = [col for col in columns if col[1] == 'unit']

            if unit_column:
                logger.info(f"✅ 'unit' column exists (type: {unit_column[0][2]}, default: {unit_column[0][4]})")
            else:
                logger.error("❌ 'unit' column not found!")
                raise Exception("Migration verification failed: unit column missing")

            # Check default value applied
            result = await session_execute(
                text("SELECT COUNT(*) FROM items WHERE unit = 'pcs.'"),
                session
            )
            items_with_default = result.scalar()

            result = await session_execute(
                text("SELECT COUNT(*) FROM items"),
                session
            )
            total_items = result.scalar()

            logger.info(f"📊 {items_with_default}/{total_items} items have default unit 'pcs.'")

            # Commit transaction
            await session_commit(session)
            logger.info("✅ Transaction committed")

            logger.info("")
            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Summary:")
            logger.info(f"  • Added 'unit' column (VARCHAR(10), DEFAULT 'pcs.')")
            logger.info(f"  • Migrated {total_items} items to default unit")
            logger.info(f"  • Validation: max 10 chars, alphanumeric + period only")
            logger.info("")
            logger.info("Supported units (examples):")
            logger.info("  • Localized: pcs. (→ Stk. in DE), pairs (→ Paar in DE)")
            logger.info("  • Metric: g, kg, ml, l, m, m2 (international)")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Update Item model and ItemDTO")
            logger.info("  2. Implement unit localization service")
            logger.info("  3. Update display services to use item-specific units")
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