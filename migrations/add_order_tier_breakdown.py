#!/usr/bin/env python3
"""
Migration: Add tier_breakdown_json to Orders
Date: 2025-11-07

This migration:
1. Adds tier_breakdown_json column to orders table
2. Stores complete tier pricing calculation with order for historical accuracy

Purpose:
- Eliminate redundant tier pricing recalculations
- Preserve pricing details for audit/transparency
- Maintain historical accuracy if prices change

Usage:
    python migrations/add_order_tier_breakdown.py
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
    """Execute the order tier breakdown migration."""
    logger.info("=" * 60)
    logger.info("ORDER TIER BREAKDOWN MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Add tier_breakdown_json column to orders table
            logger.info("Step 1: Adding tier_breakdown_json column to orders table...")
            await session.execute(text("""
                ALTER TABLE orders
                ADD COLUMN tier_breakdown_json TEXT NULL
            """))
            await session_commit(session)
            logger.info("✓ Column tier_breakdown_json added to orders table")
            logger.info("")

            # Step 2: Verification
            logger.info("Step 2: Verifying schema changes...")
            result = await session.execute(text("PRAGMA table_info(orders)"))
            columns = result.fetchall()

            tier_breakdown_exists = any(col[1] == 'tier_breakdown_json' for col in columns)

            if tier_breakdown_exists:
                logger.info("✓ Schema verification passed")
                logger.info("")
            else:
                raise Exception("Schema verification failed: tier_breakdown_json column not found")

            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Note: Existing orders will have NULL tier_breakdown_json.")
            logger.info("New orders will populate this field automatically.")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
