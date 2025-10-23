"""
Address Encryption Utility

Provides AES-256-GCM encryption/decryption for shipping addresses.
Uses key from environment variable SHIPPING_ADDRESS_ENCRYPTION_KEY.

Security:
- AES-256-GCM (Galois/Counter Mode) provides authenticated encryption
- Random nonce generated for each encryption (stored with ciphertext)
- Key must be 32 bytes (generated via: openssl rand -hex 32)
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class AddressEncryption:
    """Handles encryption/decryption of shipping addresses"""

    @staticmethod
    def _get_key() -> bytes:
        """
        Get encryption key from environment.

        Returns:
            32-byte encryption key

        Raises:
            ValueError: If key not configured or invalid length
        """
        key_hex = os.getenv("SHIPPING_ADDRESS_ENCRYPTION_KEY")

        if not key_hex:
            raise ValueError(
                "SHIPPING_ADDRESS_ENCRYPTION_KEY not configured in environment. "
                "Generate with: openssl rand -hex 32"
            )

        key = bytes.fromhex(key_hex)

        if len(key) != 32:
            raise ValueError(
                f"Encryption key must be 32 bytes (64 hex chars), got {len(key)} bytes"
            )

        return key

    @staticmethod
    def encrypt(plaintext: str) -> bytes:
        """
        Encrypt address string.

        Args:
            plaintext: Address as plain string

        Returns:
            Encrypted bytes (nonce + ciphertext + tag)

        Example:
            >>> encrypted = AddressEncryption.encrypt("John Doe\\nMain St 42\\n10115 Berlin")
        """
        key = AddressEncryption._get_key()
        aesgcm = AESGCM(key)

        # Generate random 96-bit nonce
        nonce = os.urandom(12)

        # Encrypt (returns ciphertext + 128-bit authentication tag)
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

        # Store nonce + ciphertext together
        return nonce + ciphertext

    @staticmethod
    def decrypt(encrypted: bytes) -> str:
        """
        Decrypt address bytes.

        Args:
            encrypted: Encrypted bytes (nonce + ciphertext + tag)

        Returns:
            Decrypted address string

        Raises:
            InvalidTag: If decryption fails (tampered data or wrong key)

        Example:
            >>> address = AddressEncryption.decrypt(encrypted_bytes)
        """
        key = AddressEncryption._get_key()
        aesgcm = AESGCM(key)

        # Extract nonce (first 12 bytes) and ciphertext (rest)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]

        # Decrypt and verify authentication tag
        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode('utf-8')
        except InvalidTag:
            raise ValueError("Decryption failed - data may be corrupted or key is incorrect")
