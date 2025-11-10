#!/usr/bin/env python3
"""
Migration: Add cancellation_reason to Orders
Date: 2025-11-09

This migration:
1. Adds cancellation_reason column to orders table
2. Stores custom admin cancellation reason text for display in order history

Purpose:
- Preserve admin cancellation reason for historical record
- Display reason in order detail view (user profile history)
- Improve transparency when orders are cancelled by admin

Usage:
    python migrations/add_order_cancellation_reason.py
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
    """Execute the cancellation reason migration."""
    logger.info("=" * 60)
    logger.info("ORDER CANCELLATION REASON MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Add cancellation_reason column to orders table
            logger.info("Step 1: Adding cancellation_reason column to orders table...")
            await session.execute(text("""
                ALTER TABLE orders
                ADD COLUMN cancellation_reason TEXT NULL
            """))
            await session_commit(session)
            logger.info("✓ Column cancellation_reason added to orders table")
            logger.info("")

            # Step 2: Verification
            logger.info("Step 2: Verifying schema changes...")
            result = await session.execute(text("PRAGMA table_info(orders)"))
            columns = result.fetchall()

            cancellation_reason_exists = any(col[1] == 'cancellation_reason' for col in columns)

            if cancellation_reason_exists:
                logger.info("✓ Schema verification passed")
                logger.info("")
            else:
                raise Exception("Schema verification failed: cancellation_reason column not found")

            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Note: Existing orders will have NULL cancellation_reason.")
            logger.info("New admin cancellations will populate this field automatically.")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
