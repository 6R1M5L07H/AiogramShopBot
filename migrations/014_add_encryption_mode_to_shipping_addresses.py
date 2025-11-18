#!/usr/bin/env python3
"""
Migration: Add encryption_mode to shipping_addresses table
Date: 2025-11-18

This migration adds encryption_mode column to shipping_addresses table
to support dual encryption modes:
- 'aes': Server-side AES-256-GCM encryption (existing behavior)
- 'pgp': Client-side PGP encryption (zero-knowledge, new feature)

Usage:
    python migrations/014_add_encryption_mode_to_shipping_addresses.py
"""

import sys
import os
import asyncio
import logging

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


async def run_migration():
    """Execute the encryption_mode migration."""
    logger.info("=" * 60)
    logger.info("ADD ENCRYPTION_MODE TO SHIPPING_ADDRESSES")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            logger.info("Adding encryption_mode column to shipping_addresses...")
            try:
                await session_execute(text("""
                    ALTER TABLE shipping_addresses
                    ADD COLUMN encryption_mode TEXT NOT NULL DEFAULT 'aes'
                """), session)
                logger.info("✅ encryption_mode column added")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  encryption_mode column already exists, skipping")
                else:
                    raise

            # Commit changes
            await session_commit(session)
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        sys.exit(1)