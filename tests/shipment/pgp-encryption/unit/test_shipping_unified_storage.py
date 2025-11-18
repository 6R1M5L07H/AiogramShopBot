"""
Unit tests for ShippingService unified storage (PGP + AES-GCM).

Tests save_shipping_address_unified() and get_shipping_address_unified().
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from models.order import Order
from models.user import User
from services.encryption_wrapper import EncryptionWrapper
from repositories.order import OrderRepository


@pytest_asyncio.fixture
async def pgp_test_user(test_session):
    """Create test user for PGP tests."""
    from models.cart import Cart

    user = User(
        telegram_id=999888777,
        telegram_username="pgp_testuser",
        top_up_amount=100.0
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    # Create cart for user (required by User model relationship)
    cart = Cart(user_id=user.id)
    test_session.add(cart)
    await test_session.commit()

    return user


@pytest_asyncio.fixture
async def pgp_test_order(test_session, pgp_test_user):
    """Create test order for PGP tests."""
    from models.order import OrderStatus
    from enums.currency import Currency
    from datetime import datetime, timedelta

    order = Order(
        user_id=pgp_test_user.id,
        total_price=50.0,
        currency=Currency.EUR,
        status=OrderStatus.PENDING_PAYMENT,
        expires_at=datetime.now() + timedelta(minutes=30)
    )
    test_session.add(order)
    await test_session.commit()
    await test_session.refresh(order)
    return order


class TestUnifiedStorageAESMode:
    """Test unified storage with AES-GCM encryption mode."""

    @pytest.mark.asyncio
    async def test_save_aes_mode(self, test_session, pgp_test_order):
        """Test saving shipping address with AES-GCM encryption."""
        from sqlalchemy import select
        from db import session_execute

        plaintext = "John Doe\n123 Main St\n12345 Berlin"
        order_id = pgp_test_order.id

        await EncryptionWrapper.save_shipping_address_unified(
            order_id,
            plaintext,
            "aes-gcm",
            test_session
        )

        # Reload order directly from database to get updated values
        stmt = select(Order).where(Order.id == order_id)
        result = await session_execute(stmt, test_session)
        reloaded_order = result.scalar_one()

        # Verify stored
        assert reloaded_order.encryption_mode == "aes-gcm"
        assert reloaded_order.encrypted_payload is not None
        assert isinstance(reloaded_order.encrypted_payload, bytes)
        assert len(reloaded_order.encrypted_payload) > 0

    @pytest.mark.asyncio
    async def test_retrieve_aes_mode(self, test_session, pgp_test_order):
        """Test retrieving shipping address with AES-GCM decryption."""
        plaintext = "John Doe\n123 Main St\n12345 Berlin"

        # Save
        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            plaintext,
            "aes-gcm",
            test_session
        )

        # Retrieve
        decrypted = await EncryptionWrapper.get_shipping_address_unified(
            pgp_test_order.id,
            test_session
        )

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_aes_mode_roundtrip_unicode(self, test_session, pgp_test_order):
        """Test AES-GCM roundtrip with unicode characters."""
        plaintext = "Jürgen Müller\nStraße 123\n12345 München"

        # Save
        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            plaintext,
            "aes-gcm",
            test_session
        )

        # Retrieve
        decrypted = await EncryptionWrapper.get_shipping_address_unified(
            pgp_test_order.id,
            test_session
        )

        assert decrypted == plaintext


class TestUnifiedStoragePGPMode:
    """Test unified storage with PGP encryption mode."""

    @pytest.mark.asyncio
    async def test_save_pgp_mode(self, test_session, pgp_test_order):
        """Test saving PGP-encrypted shipping address."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            pgp_message,
            "pgp",
            test_session
        )

        # Refresh order
        await test_session.refresh(pgp_test_order)

        # Verify stored
        assert pgp_test_order.encryption_mode == "pgp"
        assert pgp_test_order.encrypted_payload is not None
        assert isinstance(pgp_test_order.encrypted_payload, bytes)

    @pytest.mark.asyncio
    async def test_retrieve_pgp_mode(self, test_session, pgp_test_order):
        """Test retrieving PGP-encrypted message (no decryption)."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        # Save
        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            pgp_message,
            "pgp",
            test_session
        )

        # Retrieve (should return PGP message as-is)
        retrieved = await EncryptionWrapper.get_shipping_address_unified(
            pgp_test_order.id,
            test_session
        )

        assert retrieved == pgp_message

    @pytest.mark.asyncio
    async def test_pgp_mode_stored_as_utf8(self, test_session, pgp_test_order):
        """Test that PGP message is stored as UTF-8 encoded bytes."""
        pgp_message = """-----BEGIN PGP MESSAGE-----

hQEMA1234567890ABCAQf/abcdefghijklmnopqrstuvwxyz
-----END PGP MESSAGE-----"""

        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            pgp_message,
            "pgp",
            test_session
        )

        # Refresh order
        await test_session.refresh(pgp_test_order)

        # Verify UTF-8 encoding
        assert pgp_test_order.encrypted_payload == pgp_message.encode('utf-8')


class TestUnifiedStorageEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_invalid_encryption_mode(self, test_session, pgp_test_order):
        """Test that invalid encryption mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid encryption mode"):
            await EncryptionWrapper.save_shipping_address_unified(
                pgp_test_order.id,
                "Some address",
                "invalid-mode",
                test_session
            )

    @pytest.mark.asyncio
    async def test_retrieve_no_address(self, test_session, pgp_test_order):
        """Test retrieving from order with no shipping address."""
        # Don't save any address
        result = await EncryptionWrapper.get_shipping_address_unified(
            pgp_test_order.id,
            test_session
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_aes_mode_empty_string(self, test_session, pgp_test_order):
        """Test AES-GCM mode with empty string."""
        plaintext = ""

        await EncryptionWrapper.save_shipping_address_unified(
            pgp_test_order.id,
            plaintext,
            "aes-gcm",
            test_session
        )

        decrypted = await EncryptionWrapper.get_shipping_address_unified(
            pgp_test_order.id,
            test_session
        )

        assert decrypted == plaintext
