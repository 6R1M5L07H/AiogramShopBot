#!/usr/bin/env python3
"""
Migration: Add Sales Analytics Tables
Date: 2025-11-11

This migration creates two new tables for anonymized, long-term analytics:

1. sales_records - Anonymized sales data per item (NO user_id)
   - Retained indefinitely for trend analysis
   - One record per sold item
   - Includes temporal, financial, and product data

2. violation_statistics - Anonymized violation tracking (NO user_id)
   - Tracks payment violations, timeouts, late cancellations
   - Used for abuse pattern detection
   - Includes financial impact and penalty data

Data Minimization:
- NO user identification in either table
- Old orders can be deleted after 30 days
- Statistics remain for business intelligence

Usage:
    python migrations/add_sales_analytics_tables.py
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
    """Execute the sales analytics migration."""
    logger.info("=" * 70)
    logger.info("SALES ANALYTICS TABLES MIGRATION")
    logger.info("=" * 70)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Create sales_records table
            logger.info("Step 1: Creating sales_records table...")
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS sales_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Temporal Data
                    sale_date DATE NOT NULL,
                    sale_hour INTEGER NOT NULL CHECK (sale_hour >= 0 AND sale_hour <= 23),
                    sale_weekday INTEGER NOT NULL CHECK (sale_weekday >= 0 AND sale_weekday <= 6),

                    -- Item Details
                    category_name TEXT NOT NULL,
                    subcategory_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    is_physical BOOLEAN NOT NULL,

                    -- Financial Data
                    item_total_price REAL NOT NULL CHECK (item_total_price > 0),
                    currency TEXT NOT NULL,
                    average_unit_price REAL NOT NULL CHECK (average_unit_price > 0),
                    tier_breakdown_json TEXT NULL,

                    -- Order-Level Data (denormalized)
                    order_total_price REAL NOT NULL CHECK (order_total_price > 0),
                    order_shipping_cost REAL NOT NULL DEFAULT 0.0,
                    order_wallet_used REAL NOT NULL DEFAULT 0.0,

                    -- Payment Details
                    payment_method TEXT NULL,
                    crypto_currency TEXT NULL,

                    -- Status & Lifecycle
                    status TEXT NOT NULL,
                    is_refunded BOOLEAN NOT NULL DEFAULT 0,

                    -- Shipping Details (anonymized)
                    shipping_type TEXT NULL,

                    -- Metadata
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("✅ sales_records table created")

            # Step 2: Create indexes for sales_records
            logger.info("Step 2: Creating indexes for sales_records...")
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sales_records_sale_date
                ON sales_records(sale_date DESC)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sales_records_category
                ON sales_records(category_name, sale_date DESC)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sales_records_subcategory
                ON sales_records(subcategory_name, sale_date DESC)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sales_records_is_refunded
                ON sales_records(is_refunded, sale_date DESC)
            """))
            logger.info("✅ sales_records indexes created")

            # Step 3: Create violation_statistics table
            logger.info("Step 3: Creating violation_statistics table...")
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS violation_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Temporal Data
                    violation_date DATE NOT NULL,

                    -- Violation Type
                    violation_type TEXT NOT NULL,

                    -- Financial Impact
                    order_value REAL NOT NULL CHECK (order_value > 0),
                    penalty_applied REAL NOT NULL DEFAULT 0.0 CHECK (penalty_applied >= 0),

                    -- Retry Information
                    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),

                    -- Metadata
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("✅ violation_statistics table created")

            # Step 4: Create indexes for violation_statistics
            logger.info("Step 4: Creating indexes for violation_statistics...")
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_violation_statistics_date
                ON violation_statistics(violation_date DESC)
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_violation_statistics_type
                ON violation_statistics(violation_type, violation_date DESC)
            """))
            logger.info("✅ violation_statistics indexes created")

            # Commit all changes
            await session_commit(session)
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            logger.info("")
            logger.info("Created tables:")
            logger.info("  - sales_records (with 4 indexes)")
            logger.info("  - violation_statistics (with 2 indexes)")
            logger.info("")
            logger.info("Data Minimization:")
            logger.info("  ✅ NO user_id in either table")
            logger.info("  ✅ Anonymized data safe for indefinite retention")
            logger.info("  ✅ Orders can be deleted after 30 days")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
