#!/usr/bin/env python3
"""
Migration: Add shipping_type_key to Orders
Date: 2025-11-12

This migration:
1. Adds shipping_type_key column to orders table
2. Stores reference to shipping type from shipping_types configuration

Purpose:
- Track which shipping type is selected for an order
- Enable shipping upselling functionality
- Support dynamic shipping type selection per order
- Reference keys from shipping_types/*.json config (e.g., "paeckchen", "paket_2kg")

Usage:
    python migrations/add_shipping_type_key_to_orders.py
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
    """Execute the shipping_type_key migration."""
    logger.info("=" * 60)
    logger.info("SHIPPING TYPE KEY MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Add shipping_type_key column to orders table
            logger.info("Step 1: Adding shipping_type_key column to orders table...")
            await session.execute(text("""
                ALTER TABLE orders
                ADD COLUMN shipping_type_key VARCHAR(100) NULL
            """))
            await session_commit(session)
            logger.info("✓ Column shipping_type_key added to orders table")
            logger.info("")

            # Step 2: Verification
            logger.info("Step 2: Verifying schema changes...")
            result = await session.execute(text("PRAGMA table_info(orders)"))
            columns = result.fetchall()

            shipping_type_key_exists = any(col[1] == 'shipping_type_key' for col in columns)

            if shipping_type_key_exists:
                logger.info("✓ Schema verification passed")
                logger.info("")
            else:
                raise Exception("Schema verification failed: shipping_type_key column not found")

            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Note: Existing orders will have NULL shipping_type_key.")
            logger.info("New orders will have shipping_type_key set during order creation.")
            logger.info("Valid keys reference shipping_types/*.json configuration.")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
