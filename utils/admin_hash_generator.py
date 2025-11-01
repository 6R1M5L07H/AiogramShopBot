"""
Admin ID Hash Generator

Generates SHA256 hashes for Telegram admin IDs to prevent identification
of admin accounts if environment variables are compromised.

Usage:
    python -m utils.admin_hash_generator <telegram_id>

Example:
    python -m utils.admin_hash_generator 123456789
    Output: abc123def456...
"""

import hashlib
import sys


def generate_admin_id_hash(telegram_id: int | str) -> str:
    """
    Generates SHA256 hash of a Telegram ID for secure admin verification.

    Args:
        telegram_id: Telegram user ID (int or string)

    Returns:
        Hexadecimal SHA256 hash string

    Security Notes:
        - Uses SHA256 for cryptographic strength
        - Hashing prevents reverse lookup of admin IDs
        - Telegram ID space is large (64-bit), making brute force impractical
    """
    # Convert to string and encode
    id_string = str(telegram_id)
    id_bytes = id_string.encode('utf-8')

    # Generate SHA256 hash
    hash_obj = hashlib.sha256(id_bytes)
    return hash_obj.hexdigest()


def verify_admin_id(telegram_id: int | str, hash_list: list[str]) -> bool:
    """
    Verifies if a Telegram ID matches any of the admin hashes.

    Args:
        telegram_id: Telegram user ID to verify
        hash_list: List of SHA256 hashes of authorized admin IDs

    Returns:
        True if ID matches an admin hash, False otherwise

    Example:
        >>> admin_hashes = ["abc123...", "def456..."]
        >>> verify_admin_id(123456789, admin_hashes)
        True
    """
    user_hash = generate_admin_id_hash(telegram_id)
    return user_hash in hash_list


def main():
    """Command-line interface for hash generation."""
    if len(sys.argv) != 2:
        print("Usage: python -m utils.admin_hash_generator <telegram_id>")
        print("\nExample:")
        print("  python -m utils.admin_hash_generator 123456789")
        sys.exit(1)

    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid Telegram ID (must be an integer)")
        sys.exit(1)

    admin_hash = generate_admin_id_hash(telegram_id)

    print(f"\nTelegram ID: {telegram_id}")
    print(f"SHA256 Hash: {admin_hash}")
    print("\nAdd this hash to your .env file:")
    print(f"ADMIN_ID_HASHES={admin_hash}")
    print("\nFor multiple admins, separate with commas:")
    print(f"ADMIN_ID_HASHES={admin_hash},<hash2>,<hash3>")


if __name__ == "__main__":
    main()
