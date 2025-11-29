"""
Generic Encryption Service

Provides reusable encryption primitives for sensitive data fields.
Supports AES-256-GCM (server-side) and PGP (client-side) encryption modes.

This is a pure crypto library with no database dependencies.
Business logic and storage should be handled by domain services (e.g., ShippingService).

Security Layers:
1. PGP (client-side, asymmetric) - highest security, no server-side keys
2. AES-256-GCM (server-side, symmetric) - fallback when PGP unavailable
3. SQLCipher (database encryption) - additional layer for all data

Usage:
    # AES encryption for shipping address
    ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
        plaintext="123 Main St, City, ZIP",
        salt_component="order_12345",
        secret=config.SHIPPING_ADDRESS_SECRET
    )

    # PGP encoding (client already encrypted)
    pgp_bytes = EncryptionService.encode_pgp(pgp_armored_message)
"""

import os
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

import config

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Generic encryption service for sensitive data fields.

    This service provides low-level encryption primitives without database coupling.
    Use this for encrypting any sensitive data: shipping addresses, payment details,
    user notes, etc.

    Design Principles:
    - Pure functions (no side effects, no DB access)
    - Configurable secrets (different secrets for different data types)
    - Generic salt components (order_id, user_id, transaction_id, etc.)
    - Testable in isolation
    """

    # ========================================================================
    # AES-256-GCM Encryption (Server-Side)
    # ========================================================================

    @staticmethod
    def _derive_aes_key(salt_component: str, secret: str) -> bytes:
        """
        Derive AES encryption key from master secret + salt using PBKDF2.

        Args:
            salt_component: Unique component for key derivation (e.g., "order_123", "user_456")
            secret: Master secret from config

        Returns:
            32-byte encryption key

        Raises:
            ValueError: If secret is empty
        """
        if not secret:
            raise ValueError("Encryption secret cannot be empty")

        # Combine secret and salt component for unique key per entity
        salt = secret.encode() + salt_component.encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=100000,  # OWASP recommendation (2023)
        )
        return kdf.derive(secret.encode())

    @staticmethod
    def encrypt_aes_gcm(
        plaintext: str,
        salt_component: str,
        secret: str | None = None
    ) -> tuple[bytes, bytes, bytes]:
        """
        Encrypt plaintext with AES-256-GCM (server-side).

        Args:
            plaintext: Plain text to encrypt
            salt_component: Unique component for key derivation (e.g., "order_123")
            secret: Master secret (defaults to SHIPPING_ADDRESS_SECRET)

        Returns:
            Tuple of (ciphertext, nonce, tag) for separate field storage

        Raises:
            ValueError: If plaintext or secret is empty

        Example:
            >>> ciphertext, nonce, tag = EncryptionService.encrypt_aes_gcm(
            ...     plaintext="Sensitive Data",
            ...     salt_component="order_123"
            ... )
            >>> # Store in DB: encrypted_data=ciphertext, nonce=nonce, tag=tag
        """
        if not plaintext:
            raise ValueError("Plaintext cannot be empty")

        # Use default if None, but reject explicit empty string
        if secret is None:
            secret = config.SHIPPING_ADDRESS_SECRET

        key = EncryptionService._derive_aes_key(salt_component, secret)
        aesgcm = AESGCM(key)

        # Generate random 96-bit nonce (GCM standard)
        nonce = os.urandom(12)
        plaintext_bytes = plaintext.encode('utf-8')

        # GCM mode returns ciphertext + tag concatenated
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)

        # Split ciphertext and authentication tag
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        return ciphertext, nonce, tag

    @staticmethod
    def decrypt_aes_gcm(
        ciphertext: bytes,
        nonce: bytes,
        tag: bytes,
        salt_component: str,
        secret: str | None = None
    ) -> str:
        """
        Decrypt AES-256-GCM encrypted data.

        Args:
            ciphertext: Encrypted data
            nonce: GCM nonce (12 bytes)
            tag: GCM authentication tag (16 bytes)
            salt_component: Unique component used during encryption
            secret: Master secret (defaults to SHIPPING_ADDRESS_SECRET)

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If secret is empty
            Exception: If decryption fails (wrong key, corrupted data, tampered tag)

        Example:
            >>> plaintext = EncryptionService.decrypt_aes_gcm(
            ...     ciphertext=encrypted_data,
            ...     nonce=stored_nonce,
            ...     tag=stored_tag,
            ...     salt_component="order_123"
            ... )
        """
        # Use default if None, but reject explicit empty string
        if secret is None:
            secret = config.SHIPPING_ADDRESS_SECRET

        key = EncryptionService._derive_aes_key(salt_component, secret)
        aesgcm = AESGCM(key)

        # Reconstruct ciphertext_with_tag for decryption
        ciphertext_with_tag = ciphertext + tag
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)

        return plaintext_bytes.decode('utf-8')

    # ========================================================================
    # PGP Encryption (Client-Side)
    # ========================================================================

    @staticmethod
    def encode_pgp(pgp_armored_message: str) -> bytes:
        """
        Encode PGP-encrypted message for binary storage.

        The bot does NOT perform PGP encryption - the client (Telegram Mini App)
        encrypts the message with the bot owner's public key before sending.

        This method only converts the ASCII-armored PGP message to binary format
        for database storage.

        Args:
            pgp_armored_message: ASCII-armored PGP message from client
                Format: "-----BEGIN PGP MESSAGE-----\\n...\\n-----END PGP MESSAGE-----"

        Returns:
            UTF-8 encoded binary for database storage

        Example:
            >>> pgp_message = "-----BEGIN PGP MESSAGE-----\\n...\\n-----END PGP MESSAGE-----"
            >>> pgp_bytes = EncryptionService.encode_pgp(pgp_message)
            >>> # Store in DB: encrypted_address=pgp_bytes, encryption_mode='pgp'
        """
        return pgp_armored_message.encode('utf-8')

    @staticmethod
    def decode_pgp(encrypted_payload: bytes) -> str:
        """
        Decode PGP-encrypted message from binary storage.

        Returns the ASCII-armored PGP message that can be decrypted by the bot owner
        using their private key (offline, outside the bot).

        Args:
            encrypted_payload: Binary PGP message from database

        Returns:
            ASCII-armored PGP message (cannot be decrypted by bot)

        Example:
            >>> pgp_message = EncryptionService.decode_pgp(encrypted_payload)
            >>> print(pgp_message)
            -----BEGIN PGP MESSAGE-----
            ...
            -----END PGP MESSAGE-----
        """
        return encrypted_payload.decode('utf-8')

    # ========================================================================
    # Validation Helpers
    # ========================================================================

    @staticmethod
    def validate_encryption_mode(encryption_mode: str) -> bool:
        """
        Validate encryption mode value.

        Args:
            encryption_mode: Encryption mode to validate

        Returns:
            True if valid, False otherwise

        Valid modes:
            - 'aes': AES-256-GCM server-side encryption
            - 'pgp': PGP client-side encryption
        """
        return encryption_mode in ('aes', 'pgp')

    @staticmethod
    def is_pgp_available() -> bool:
        """
        Check if PGP encryption is available (public key configured).

        Returns:
            True if PGP is configured and available, False otherwise
        """
        return bool(config.PGP_PUBLIC_KEY_BASE64)
