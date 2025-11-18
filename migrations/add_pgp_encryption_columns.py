#!/usr/bin/env python3
"""
Migration: Add PGP Encryption Support for Shipping Addresses
Date: 2025-11-16

This migration:
1. Adds encryption_mode column to orders (TEXT, nullable)
2. Adds encrypted_payload column to orders (BLOB, nullable)

These columns support dual encryption modes:
- 'aes-gcm': Server-side AES-256-GCM encryption (fallback)
- 'pgp': Client-side PGP encryption (zero-knowledge)

Usage:
    python migrations/add_pgp_encryption_columns.py
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
    """Execute the PGP encryption columns migration."""
    logger.info("=" * 60)
    logger.info("PGP ENCRYPTION COLUMNS MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Add encryption_mode column
            logger.info("Step 1: Adding encryption_mode column to orders...")
            try:
                await session.execute(text("""
                    ALTER TABLE orders ADD COLUMN encryption_mode TEXT NULL
                """))
                logger.info("✅ encryption_mode column added")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  encryption_mode column already exists, skipping")
                else:
                    raise

            # Step 2: Add encrypted_payload column
            logger.info("Step 2: Adding encrypted_payload column to orders...")
            try:
                await session.execute(text("""
                    ALTER TABLE orders ADD COLUMN encrypted_payload BLOB NULL
                """))
                logger.info("✅ encrypted_payload column added")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  encrypted_payload column already exists, skipping")
                else:
                    raise

            # Commit changes
            await session_commit(session)
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ PGP ENCRYPTION MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. Configure PGP_PUBLIC_KEY_BASE64 in .env")
            logger.info("2. Configure BOT_DOMAIN in .env")
            logger.info("3. Generate PGP keypair: bash tools/setup_pgp_keys.sh")
            logger.info("4. Restart bot to enable encrypted address input")
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
