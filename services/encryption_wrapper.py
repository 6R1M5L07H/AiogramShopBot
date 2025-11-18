"""
Unified Encryption Wrapper for Shipping Addresses

Handles both AES-256-GCM (server-side) and PGP (client-side) encryption modes.
Works with unified orders.encrypted_payload storage.
"""

import os
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

import config
from db import session_execute, session_commit
from models.order import Order
from exceptions.shipping import PGPKeyNotConfiguredException


logger = logging.getLogger(__name__)


class EncryptionWrapper:
    """
    Unified encryption wrapper for shipping addresses.

    Supports two modes:
    1. AES-GCM: Server-side encryption with AES-256-GCM
    2. PGP: Client-side encryption (Mini App sends pre-encrypted data)

    Storage format in orders.encrypted_payload:
    - AES-GCM: [ciphertext][nonce 12 bytes][tag 16 bytes]
    - PGP: UTF-8 encoded ASCII-armored PGP message
    """

    # ========================================================================
    # AES-256-GCM Encryption (Server-Side)
    # ========================================================================

    @staticmethod
    def _derive_aes_key(order_id: int) -> bytes:
        """
        Derive AES encryption key from master secret + order_id using PBKDF2.

        Args:
            order_id: Order ID used as salt component

        Returns:
            32-byte encryption key
        """
        salt = config.SHIPPING_ADDRESS_SECRET.encode() + str(order_id).encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(config.SHIPPING_ADDRESS_SECRET.encode())

    @staticmethod
    def encrypt_aes_gcm(plaintext: str, order_id: int) -> bytes:
        """
        Encrypt plaintext with AES-256-GCM (server-side).

        Args:
            plaintext: Plain text shipping address
            order_id: Order ID for key derivation

        Returns:
            Combined binary: [ciphertext][nonce 12 bytes][tag 16 bytes]
        """
        key = EncryptionWrapper._derive_aes_key(order_id)
        aesgcm = AESGCM(key)

        nonce = os.urandom(12)  # 96-bit nonce for GCM
        plaintext_bytes = plaintext.encode('utf-8')

        # GCM mode returns ciphertext + tag concatenated
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)

        # Split ciphertext and tag
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        # Combine: [ciphertext][nonce][tag]
        combined = ciphertext + nonce + tag

        return combined

    @staticmethod
    def decrypt_aes_gcm(combined: bytes, order_id: int) -> str:
        """
        Decrypt AES-256-GCM encrypted data.

        Args:
            combined: Combined binary [ciphertext][nonce 12 bytes][tag 16 bytes]
            order_id: Order ID for key derivation

        Returns:
            Decrypted plaintext shipping address

        Raises:
            Exception: If decryption fails (wrong key, corrupted data)
        """
        key = EncryptionWrapper._derive_aes_key(order_id)
        aesgcm = AESGCM(key)

        # Extract components from combined binary
        nonce = combined[-28:-16]  # Last 28 bytes = nonce (12) + tag (16)
        tag = combined[-16:]
        ciphertext = combined[:-28]

        # Reconstruct ciphertext_with_tag for decryption
        ciphertext_with_tag = ciphertext + tag
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)

        return plaintext_bytes.decode('utf-8')

    # ========================================================================
    # PGP Encryption (Client-Side)
    # ========================================================================

    @staticmethod
    def store_pgp_encrypted(pgp_message: str) -> bytes:
        """
        Store PGP-encrypted message as binary.

        Args:
            pgp_message: ASCII-armored PGP message from Mini App

        Returns:
            UTF-8 encoded binary for database storage
        """
        return pgp_message.encode('utf-8')

    @staticmethod
    def load_pgp_encrypted(encrypted_payload: bytes) -> str:
        """
        Load PGP-encrypted message from binary storage.

        Args:
            encrypted_payload: Binary PGP message from database

        Returns:
            ASCII-armored PGP message (cannot be decrypted by bot)
        """
        return encrypted_payload.decode('utf-8')

    # ========================================================================
    # Unified Storage Interface
    # ========================================================================

    @staticmethod
    async def save_shipping_address_unified(
        order_id: int,
        plaintext_or_pgp: str,
        encryption_mode: str,
        session: AsyncSession | Session
    ):
        """
        Save shipping address with unified storage.

        Args:
            order_id: Order ID
            plaintext_or_pgp: Plaintext (for AES) or PGP message (for PGP mode)
            encryption_mode: 'aes-gcm' or 'pgp'
            session: Database session

        Raises:
            ValueError: If invalid encryption mode
        """
        # Get order directly from database (not via repository which returns DTO)
        stmt = select(Order).where(Order.id == order_id)
        result = await session_execute(stmt, session)
        order = result.scalar_one()

        if encryption_mode == "aes-gcm":
            # Server-side AES encryption
            encrypted_payload = EncryptionWrapper.encrypt_aes_gcm(plaintext_or_pgp, order_id)
        elif encryption_mode == "pgp":
            # Client-side PGP (already encrypted)
            encrypted_payload = EncryptionWrapper.store_pgp_encrypted(plaintext_or_pgp)
        else:
            raise ValueError(f"Invalid encryption mode: {encryption_mode}")

        # Update order
        order.encryption_mode = encryption_mode
        order.encrypted_payload = encrypted_payload

        await session_commit(session)
        logger.info(f"Saved shipping address for order {order_id} with {encryption_mode} encryption")

    @staticmethod
    async def get_shipping_address_unified(
        order_id: int,
        session: AsyncSession | Session
    ) -> str | None:
        """
        Retrieve shipping address from unified storage.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            - AES mode: Decrypted plaintext address
            - PGP mode: ASCII-armored PGP message (admin must decrypt offline)
            - None if no address stored

        Raises:
            ValueError: If decryption fails or invalid encryption mode
        """
        # Get order directly from database
        stmt = select(Order).where(Order.id == order_id)
        result = await session_execute(stmt, session)
        order = result.scalar_one()

        if not order.encrypted_payload:
            return None

        if order.encryption_mode == "aes-gcm":
            # Server-side decryption
            try:
                return EncryptionWrapper.decrypt_aes_gcm(order.encrypted_payload, order_id)
            except Exception as e:
                from utils.localizator import Localizator
                from enums.bot_entity import BotEntity
                logger.error(f"Failed to decrypt AES-GCM address for order {order_id}: {e}")
                return Localizator.get_text(BotEntity.ADMIN, "decryption_failed_message")

        elif order.encryption_mode == "pgp":
            # Return PGP message as-is (admin must decrypt offline)
            return EncryptionWrapper.load_pgp_encrypted(order.encrypted_payload)

        else:
            logger.error(f"Unknown encryption mode '{order.encryption_mode}' for order {order_id}")
            return "[UNKNOWN ENCRYPTION MODE]"
