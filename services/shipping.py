"""
Shipping Service

Handles shipping address encryption, storage, and retrieval for orders with physical items.
Uses AES-256-GCM encryption with PBKDF2 key derivation.
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

import config
from db import session_execute, session_commit
from models.shipping_address import ShippingAddress
from utils.html_escape import safe_html


class ShippingService:

    @staticmethod
    def _derive_key(order_id: int) -> bytes:
        """
        Derive encryption key from master secret + order_id using PBKDF2.

        Args:
            order_id: Order ID used as salt component

        Returns:
            32-byte encryption key
        """
        # Use order_id as part of salt for order-specific keys
        salt = config.SHIPPING_ADDRESS_SECRET.encode() + str(order_id).encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(config.SHIPPING_ADDRESS_SECRET.encode())

    @staticmethod
    def encrypt_address(plaintext_address: str, order_id: int) -> tuple[bytes, bytes, bytes]:
        """
        Encrypt shipping address using AES-256-GCM.

        Args:
            plaintext_address: Plain text shipping address
            order_id: Order ID for key derivation

        Returns:
            (encrypted_data, nonce, tag)
        """
        key = ShippingService._derive_key(order_id)
        aesgcm = AESGCM(key)

        nonce = os.urandom(12)  # 96-bit nonce for GCM
        plaintext_bytes = plaintext_address.encode('utf-8')

        # GCM mode returns ciphertext + tag concatenated
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)

        # Split ciphertext and tag (last 16 bytes are tag)
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        return ciphertext, nonce, tag

    @staticmethod
    def decrypt_address(encrypted_address: bytes, nonce: bytes, tag: bytes, order_id: int) -> str:
        """
        Decrypt shipping address using AES-256-GCM.

        Args:
            encrypted_address: Encrypted address data
            nonce: GCM nonce
            tag: GCM authentication tag
            order_id: Order ID for key derivation

        Returns:
            Decrypted plain text address
        """
        key = ShippingService._derive_key(order_id)
        aesgcm = AESGCM(key)

        # Concatenate ciphertext and tag for GCM decryption
        ciphertext_with_tag = encrypted_address + tag

        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext_bytes.decode('utf-8')

    @staticmethod
    async def save_shipping_address(
        order_id: int,
        plaintext_address: str,
        session: AsyncSession | Session
    ):
        """
        Encrypt and save shipping address for an order (AES mode).

        Args:
            order_id: Order ID
            plaintext_address: Plain text shipping address
            session: Database session
        """
        # Encrypt address
        encrypted, nonce, tag = ShippingService.encrypt_address(plaintext_address, order_id)

        # Save to database
        shipping_address = ShippingAddress(
            order_id=order_id,
            encrypted_address=encrypted,
            nonce=nonce,
            tag=tag,
            encryption_mode='aes'
        )
        session.add(shipping_address)
        await session_commit(session)

    @staticmethod
    async def save_encrypted_shipping_address(
        order_id: int,
        encrypted_address: str,
        encryption_mode: str,
        user_id: int,
        session: AsyncSession | Session
    ):
        """
        Save PGP/AES encrypted shipping address from WebApp.

        Business logic:
        - Validates order ownership (user must own the order)
        - Validates order status (only PENDING_PAYMENT_AND_ADDRESS or PENDING_PAYMENT)
        - Stores encrypted address (no decryption - zero-knowledge)

        Args:
            order_id: Order ID
            encrypted_address: PGP or AES encrypted address string
            encryption_mode: "pgp" or "aes"
            user_id: Telegram user ID (for ownership verification)
            session: Database session

        Raises:
            OrderNotFoundException: If order not found
            OrderOwnershipException: If user doesn't own the order
            InvalidOrderStateException: If order status doesn't allow address changes
        """
        from repositories.order import OrderRepository
        from enums.order_status import OrderStatus
        from exceptions.order import (
            OrderNotFoundException,
            OrderOwnershipException,
            InvalidOrderStateException
        )

        # Get order (with error handling)
        try:
            order_dto = await OrderRepository.get_by_id(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        # Verify order ownership (compare telegram_id with telegram_id)
        from repositories.user import UserRepository
        user = await UserRepository.get_by_id(order_dto.user_id, session)
        if user.telegram_id != user_id:
            raise OrderOwnershipException(order_id, user_id)

        # Verify order status allows address changes (one-time submission only)
        if order_dto.status != OrderStatus.PENDING_PAYMENT_AND_ADDRESS:
            raise InvalidOrderStateException(
                order_id,
                current_state=order_dto.status.value,
                required_state=OrderStatus.PENDING_PAYMENT_AND_ADDRESS.value
            )

        # Save encrypted address to database
        # NOTE: We store the entire PGP message including headers
        # Format: "-----BEGIN PGP MESSAGE-----\n...\n-----END PGP MESSAGE-----"
        shipping_address = ShippingAddress(
            order_id=order_id,
            encrypted_address=encrypted_address.encode('utf-8'),
            nonce=b'',  # Not used for PGP mode
            tag=b'',    # Not used for PGP mode
            encryption_mode=encryption_mode
        )
        session.add(shipping_address)
        await session_commit(session)

        # Update order status: address requirement fulfilled
        await OrderRepository.update_status(
            order_id,
            OrderStatus.PENDING_PAYMENT,
            session
        )
        await session_commit(session)

    @staticmethod
    async def get_shipping_address(
        order_id: int,
        session: AsyncSession | Session,
        return_encrypted_for_pgp: bool = False
    ) -> str | None:
        """
        Retrieve shipping address for an order.

        Args:
            order_id: Order ID
            session: Database session
            return_encrypted_for_pgp: If True, return PGP addresses encrypted (for admin display)

        Returns:
            - AES mode: Decrypted plaintext address
            - PGP mode: Encrypted PGP block (if return_encrypted_for_pgp=True) or placeholder
            - None if not found
        """
        stmt = select(ShippingAddress).where(ShippingAddress.order_id == order_id)
        result = await session_execute(stmt, session)
        shipping_address = result.scalar_one_or_none()

        if not shipping_address:
            return None

        # PGP mode: Return encrypted block for admin display
        if shipping_address.encryption_mode == 'pgp':
            if return_encrypted_for_pgp:
                return shipping_address.encrypted_address.decode('utf-8')
            else:
                from utils.localizator import Localizator
                from enums.bot_entity import BotEntity
                return Localizator.get_text(BotEntity.ADMIN, "pgp_encrypted_placeholder")

        # AES mode: Decrypt and return
        try:
            return ShippingService.decrypt_address(
                shipping_address.encrypted_address,
                shipping_address.nonce,
                shipping_address.tag,
                order_id
            )
        except Exception as e:
            # Decryption failed (wrong key, corrupted data, etc.)
            # Log error and return fallback message
            import logging
            from utils.localizator import Localizator
            from enums.bot_entity import BotEntity
            logging.error(f"Failed to decrypt shipping address for order {order_id}: {e}")
            return Localizator.get_text(BotEntity.ADMIN, "decryption_failed_message")

    @staticmethod
    async def delete_shipping_address(
        order_id: int,
        session: AsyncSession | Session
    ):
        """
        Delete shipping address for an order (e.g., when order is cancelled).

        Args:
            order_id: Order ID
            session: Database session
        """
        stmt = select(ShippingAddress).where(ShippingAddress.order_id == order_id)
        result = await session_execute(stmt, session)
        shipping_address = result.scalar_one_or_none()

        if shipping_address:
            await session.delete(shipping_address)
            await session_commit(session)

    @staticmethod
    async def check_cart_has_physical_items(cart_items, session: AsyncSession | Session) -> bool:
        """
        Check if cart contains any physical items requiring shipping.

        Args:
            cart_items: List of CartItemDTO objects
            session: Database session

        Returns:
            True if cart has physical items, False otherwise
        """
        from repositories.item import ItemRepository
        from models.item import ItemDTO

        for cart_item in cart_items:
            item = await ItemRepository.get_item_metadata(
                cart_item.category_id,
                cart_item.subcategory_id,
                session
            )
            if item and item.is_physical:
                return True

        return False

    # ========================================================================
    # Shipping Management Business Logic
    # ========================================================================

    @staticmethod
    async def get_pending_shipments(session: AsyncSession | Session):
        """
        Get all orders awaiting shipment.

        Args:
            session: Database session

        Returns:
            List of orders with PAID_AWAITING_SHIPMENT status
        """
        from repositories.order import OrderRepository
        return await OrderRepository.get_orders_awaiting_shipment(session)

    @staticmethod
    async def get_order_display_data(order, session: AsyncSession | Session) -> dict:
        """
        Get formatted display data for an order in shipment list.

        NOTE: This method expects order.user and order.invoices to be eager-loaded
        (via selectinload) to avoid N+1 queries when called in a loop.

        Args:
            order: Order model instance (with user and invoices relationships loaded)
            session: Database session

        Returns:
            Dict with invoice_display, user_display, created_time
        """
        from datetime import datetime

        # Use already-loaded user relationship (no query!)
        user = order.user

        # Format user display
        if user and user.telegram_username:
            user_display = f"@{user.telegram_username} (ID:{user.telegram_id})"
        elif user:
            user_display = f"ID:{user.telegram_id}"
        else:
            user_display = f"ID:{order.user_id}"

        # Use already-loaded invoices relationship (no query!)
        invoices = order.invoices
        if invoices:
            # Use first invoice (or concatenate if multiple)
            invoice_display = invoices[0].invoice_number
            if len(invoices) > 1:
                invoice_display = " / ".join(inv.invoice_number for inv in invoices)
        else:
            invoice_display = "N/A"

        # Format creation time
        created_time = order.created_at.strftime("%d.%m %H:%M") if order.created_at else "N/A"

        return {
            "invoice_display": invoice_display,
            "user_display": user_display,
            "created_time": created_time
        }

    @staticmethod
    async def get_order_details_data(
        order_id: int,
        session: AsyncSession | Session,
        return_encrypted_pgp: bool = True
    ) -> dict | None:
        """
        Get complete order details including items, invoice, user, and shipping address.

        Args:
            order_id: Order ID
            session: Database session
            return_encrypted_pgp: If True, return PGP addresses encrypted (for admin view)

        Returns:
            Dict with order details or None if order not found

        Raises:
            ValueError: If order not found
        """
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        from repositories.user import UserRepository
        from datetime import datetime

        # Get order with items (with error handling)
        from exceptions.order import OrderNotFoundException

        try:
            order = await OrderRepository.get_by_id_with_items(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        invoice = await InvoiceRepository.get_by_order_id(order_id, session)
        user = await UserRepository.get_by_id(order.user_id, session)
        shipping_address = await ShippingService.get_shipping_address(
            order_id,
            session,
            return_encrypted_for_pgp=return_encrypted_pgp
        )

        # Format user display (escape for HTML safety)
        username = f"@{safe_html(user.telegram_username)}" if user.telegram_username else str(user.telegram_id)

        # Get invoice number with fallback
        if invoice:
            invoice_number = invoice.invoice_number
        else:
            invoice_number = "N/A"

        # Group items by type
        digital_items = [item for item in order.items if not item.is_physical]
        physical_items = [item for item in order.items if item.is_physical]

        # Calculate grouped items and totals
        digital_grouped = ShippingService._group_items(digital_items)
        physical_grouped = ShippingService._group_items(physical_items)

        return {
            "order": order,
            "invoice_number": invoice_number,
            "username": username,
            "user_id": user.telegram_id,
            "shipping_address": shipping_address,
            "digital_items": digital_grouped,
            "physical_items": physical_grouped,
        }

    @staticmethod
    def _group_items(items: list) -> dict:
        """
        Group items by (description, price) and count quantities.

        Args:
            items: List of order items

        Returns:
            Dict with (description, price) as key and quantity as value
        """
        grouped = {}
        for item in items:
            key = (item.description, item.price)
            if key not in grouped:
                grouped[key] = 0
            grouped[key] += 1
        return grouped

    @staticmethod
    async def mark_order_as_shipped(order_id: int, session: AsyncSession | Session) -> dict:
        """
        Mark order as shipped and send notification to user.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            Dict with invoice_number for success message

        Raises:
            ValueError: If order not found
        """
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        from enums.order_status import OrderStatus
        from services.notification import NotificationService
        from db import session_commit
        from datetime import datetime

        # Update order status
        await OrderRepository.update_status(order_id, OrderStatus.SHIPPED, session)
        await session_commit(session)

        # Get order and invoice for notification
        from exceptions.order import OrderNotFoundException

        try:
            order = await OrderRepository.get_by_id(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        invoice = await InvoiceRepository.get_by_order_id(order_id, session)

        if invoice:
            invoice_number = invoice.invoice_number
        else:
            invoice_number = "N/A"

        # Send notification to user
        await NotificationService.order_shipped(order.user_id, order_id, invoice_number, session)

        return {"invoice_number": invoice_number}

    @staticmethod
    async def get_invoice_number(order_id: int, session: AsyncSession | Session) -> str:
        """
        Get invoice number for an order with fallback.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            Invoice number string
        """
        from repositories.invoice import InvoiceRepository
        from datetime import datetime

        invoice = await InvoiceRepository.get_by_order_id(order_id, session)
        if invoice:
            return invoice.invoice_number
        else:
            return "N/A"
