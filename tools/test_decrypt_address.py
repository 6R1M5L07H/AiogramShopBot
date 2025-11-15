#!/usr/bin/env python3
"""
Test Script: Decrypt PGP-encrypted Shipping Addresses

Usage:
    python tools/test_decrypt_address.py <order_id>

This script decrypts shipping addresses that were encrypted with PGP.
Requires the private key to be available in GPG keyring.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gnupg
from sqlalchemy import select

from db import get_db_session, session_execute
from models.order import Order


async def decrypt_shipping_address(order_id: int):
    """
    Decrypt and display shipping address for an order.

    Args:
        order_id: Order ID to decrypt address for
    """

    # Initialize GPG
    gpg = gnupg.GPG()

    # Check if we have any private keys
    private_keys = gpg.list_keys(True)
    if not private_keys:
        print("❌ Error: No private keys found in GPG keyring")
        print()
        print("Please import the test private key:")
        print("  gpg --import tools/test_pgp_private_key.asc")
        print()
        return

    print("=" * 60)
    print("PGP Shipping Address Decryption Test")
    print("=" * 60)
    print()
    print(f"🔍 Looking up order #{order_id}...")
    print()

    # Get order from database
    async with get_db_session() as session:
        stmt = select(Order).where(Order.id == order_id)
        result = await session_execute(stmt, session)
        order = result.scalar_one_or_none()

        if not order:
            print(f"❌ Error: Order #{order_id} not found")
            return

        if not order.encrypted_payload:
            print(f"⚠️  Order #{order_id} has no encrypted shipping address")
            return

        if order.encryption_mode != "pgp":
            print(f"⚠️  Order #{order_id} uses {order.encryption_mode} encryption, not PGP")
            print(f"   Cannot decrypt with this tool (use AES decryption)")
            return

        # Decrypt PGP message
        print(f"✅ Order found")
        print(f"   Encryption mode: {order.encryption_mode}")
        print(f"   Payload size: {len(order.encrypted_payload)} bytes")
        print()

        # Decode binary payload to ASCII-armored PGP message
        pgp_message = order.encrypted_payload.decode('utf-8')

        print("🔐 Decrypting...")
        print()

        # Decrypt
        decrypted = gpg.decrypt(pgp_message)

        if not decrypted.ok:
            print("❌ Decryption failed!")
            print(f"   Status: {decrypted.status}")
            print(f"   Error: {decrypted.stderr}")
            print()
            print("Possible reasons:")
            print("  - Private key not in keyring")
            print("  - Wrong private key")
            print("  - Corrupted encrypted data")
            return

        # Success!
        print("=" * 60)
        print("✅ Decryption Successful!")
        print("=" * 60)
        print()
        print("📬 Shipping Address:")
        print("─" * 60)
        print(str(decrypted))
        print("─" * 60)
        print()

        # Show key info
        print("🔑 Decryption Info:")
        print(f"   Key ID: {decrypted.key_id}")
        print(f"   Username: {decrypted.username}")
        print(f"   Fingerprint: {decrypted.fingerprint}")
        print()


def show_usage():
    """Show usage instructions."""
    print("Usage: python tools/test_decrypt_address.py <order_id>")
    print()
    print("Examples:")
    print("  python tools/test_decrypt_address.py 42")
    print("  python tools/test_decrypt_address.py 123")
    print()
    print("Prerequisites:")
    print("  1. Generate test key: bash tools/setup_test_pgp_key.sh")
    print("  2. Import private key: gpg --import tools/test_pgp_private_key.asc")
    print("  3. Create order with PGP-encrypted address via Mini App")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)

    try:
        order_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Error: Invalid order ID '{sys.argv[1]}' (must be a number)")
        print()
        show_usage()
        sys.exit(1)

    # Run decryption
    asyncio.run(decrypt_shipping_address(order_id))
