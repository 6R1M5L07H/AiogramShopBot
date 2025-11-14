#!/usr/bin/env python3
"""
Migration: Add order_hash to sales_records
Date: 2025-11-14

Adds the order_hash column to the sales_records table.
This column provides pseudonymized order tracking for refund analytics
without storing direct user identifiers.

Usage:
    python migrations/add_order_hash_to_sales_records.py
"""

import sys
import os
import asyncio
import logging

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
    """Execute the order_hash migration."""
    logger.info("=" * 70)
    logger.info("ADD ORDER_HASH TO SALES_RECORDS MIGRATION")
    logger.info("=" * 70)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Check if column already exists
            logger.info("Checking if order_hash column exists...")
            result = await session.execute(text("PRAGMA table_info(sales_records)"))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]

            if 'order_hash' in column_names:
                logger.info("✅ order_hash column already exists, skipping migration")
                logger.info("")
                return

            # Step 1: Add order_hash column
            logger.info("Step 1: Adding order_hash column...")
            await session.execute(text("""
                ALTER TABLE sales_records ADD COLUMN order_hash TEXT
            """))
            logger.info("✅ order_hash column added")

            # Step 2: Create index
            logger.info("Step 2: Creating index for order_hash...")
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sales_records_order_hash
                ON sales_records(order_hash)
            """))
            logger.info("✅ Index created")

            # Commit all changes
            await session_commit(session)
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            logger.info("")
            logger.info("Changes:")
            logger.info("  ✅ Added order_hash column to sales_records")
            logger.info("  ✅ Created index idx_sales_records_order_hash")
            logger.info("")
            logger.info("Purpose:")
            logger.info("  - Pseudonymized order tracking for refund analytics")
            logger.info("  - No direct user identification")
            logger.info("  - Enables refund rate analysis per order")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())