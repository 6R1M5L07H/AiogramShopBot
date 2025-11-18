#!/usr/bin/env python3
"""
Migration: Add encryption_mode to shipping_addresses table (SYNC VERSION for SQLCipher)
Date: 2025-11-18

This migration adds encryption_mode column to shipping_addresses table
to support dual encryption modes:
- 'aes': Server-side AES-256-GCM encryption (existing behavior)
- 'pgp': Client-side PGP encryption (zero-knowledge, new feature)

Usage:
    python migrations/014_add_encryption_mode_to_shipping_addresses_sync.py
"""

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_migration():
    """Execute the encryption_mode migration synchronously."""
    logger.info("=" * 60)
    logger.info("ADD ENCRYPTION_MODE TO SHIPPING_ADDRESSES (SYNC)")
    logger.info("=" * 60)
    logger.info("")

    # Create synchronous engine for SQLCipher
    if config.DB_ENCRYPTION:
        from sqlcipher3 import dbapi2 as sqlcipher
        db_path = f"/bot/data/{config.DB_NAME}"
        logger.info(f"Using SQLCipher encryption with database: {db_path}")
        # Format: sqlite+pysqlcipher://:{password}@////absolute/path (4 slashes for absolute path)
        # Must match db.py configuration exactly
        engine = create_engine(
            f"sqlite+pysqlcipher://:{config.DB_PASS}@////{db_path}",
            echo=False,
            module=sqlcipher,
            connect_args={"check_same_thread": False}
        )
    else:
        db_path = f"data/{config.DB_NAME}"
        logger.info(f"Using standard SQLite with database: {db_path}")
        engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )

    Session = sessionmaker(bind=engine)

    with Session() as session:
        try:
            logger.info("Adding encryption_mode column to shipping_addresses...")
            try:
                session.execute(text("""
                    ALTER TABLE shipping_addresses
                    ADD COLUMN encryption_mode TEXT NOT NULL DEFAULT 'aes'
                """))
                session.commit()
                logger.info("✅ encryption_mode column added")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("⚠️  encryption_mode column already exists, skipping")
                    session.rollback()
                else:
                    session.rollback()
                    raise

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
        run_migration()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        sys.exit(1)
