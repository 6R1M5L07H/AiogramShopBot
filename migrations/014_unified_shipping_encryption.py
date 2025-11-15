#!/usr/bin/env python3
"""
Migration: Unified Shipping Address Encryption Storage

Migrates existing shipping_addresses data to orders.encrypted_payload
with encryption_mode='aes-gcm'.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from models.order import Order
from models.shipping_address import ShippingAddress
from db import get_db_session, session_execute, session_commit
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_shipping_addresses():
    """Migrate shipping_addresses data to unified orders.encrypted_payload storage."""

    logger.info("Starting shipping address migration...")

    async with get_db_session() as session:
        # Find all orders with shipping addresses
        stmt = (
            select(Order, ShippingAddress)
            .join(ShippingAddress, ShippingAddress.order_id == Order.id)
        )
        result = await session_execute(stmt, session)
        rows = result.all()

        if not rows:
            logger.info("No shipping addresses to migrate")
            return

        migrated_count = 0
        for order, shipping in rows:
            # Combine AES-GCM components into single BLOB
            # Format: [ciphertext][nonce 12 bytes][tag 16 bytes]
            combined = shipping.encrypted_address + shipping.nonce + shipping.tag

            # Update order with unified storage
            order.encryption_mode = "aes-gcm"
            order.encrypted_payload = combined
            migrated_count += 1

            logger.debug(f"Migrated order {order.id}: {len(combined)} bytes")

        await session_commit(session)
        logger.info(f"✅ Successfully migrated {migrated_count} shipping addresses to unified storage")
        logger.info(f"   Old table: shipping_addresses (3 columns)")
        logger.info(f"   New storage: orders.encrypted_payload (1 BLOB + mode)")


async def verify_migration():
    """Verify migration was successful."""

    logger.info("Verifying migration...")

    async with get_db_session() as session:
        # Count migrated records
        stmt = select(Order).where(Order.encryption_mode == "aes-gcm")
        result = await session_execute(stmt, session)
        orders = result.scalars().all()

        logger.info(f"✅ Found {len(orders)} orders with encryption_mode='aes-gcm'")

        # Verify payload length (should be at least 28 bytes: nonce + tag)
        invalid_count = 0
        for order in orders:
            if order.encrypted_payload and len(order.encrypted_payload) < 28:
                logger.warning(f"⚠️  Order {order.id} has invalid payload length: {len(order.encrypted_payload)}")
                invalid_count += 1

        if invalid_count > 0:
            logger.error(f"❌ Migration verification failed: {invalid_count} invalid payloads")
            return False

        logger.info("✅ Migration verification successful")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Unified Shipping Encryption Storage")
    print("=" * 60)
    print()

    # Run migration
    asyncio.run(migrate_shipping_addresses())

    # Verify
    success = asyncio.run(verify_migration())

    if success:
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Test decryption with ShippingService.get_shipping_address_unified()")
        print("2. After verification, drop old table:")
        print("   sqlite3 data/database.db 'DROP TABLE IF EXISTS shipping_addresses;'")
    else:
        print()
        print("=" * 60)
        print("❌ Migration failed! Check logs above.")
        print("=" * 60)
        sys.exit(1)
