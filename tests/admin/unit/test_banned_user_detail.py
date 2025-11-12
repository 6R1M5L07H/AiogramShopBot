"""
Unit Tests: AdminService.get_banned_user_detail_data()

Tests the service layer method for fetching banned user details and strike history.
This method should be free of Telegram-specific logic (no CallbackQuery, no InlineKeyboardBuilder).

Run with:
    pytest tests/admin/unit/test_banned_user_detail.py -v
"""

import pytest
import sys
import os
import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.user import User
from models.user_strike import UserStrike
from models.order import Order
from models.invoice import Invoice
from enums.strike_type import StrikeType
from enums.order_status import OrderStatus
from enums.currency import Currency
from services.admin import AdminService


class TestBannedUserDetailService:
    """Test AdminService.get_banned_user_detail_data() for proper service/handler separation."""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite database."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session."""
        session = Session(engine)
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def banned_user_with_strikes(self, session):
        """Create a banned user with multiple strikes."""
        user = User(
            telegram_id=123456,
            telegram_username="test_user",
            strike_count=3,
            is_blocked=True,
            blocked_at=datetime.datetime(2025, 11, 10, 15, 30),
            blocked_reason="3 strikes reached (automatic ban)"
        )
        session.add(user)
        session.commit()

        # Create orders with invoices
        order1 = Order(
            user_id=user.id,
            total_price=50.0,
            currency=Currency.EUR,
            status=OrderStatus.CANCELLED_BY_SYSTEM,
            expires_at=datetime.datetime.now() + datetime.timedelta(minutes=30)
        )
        order2 = Order(
            user_id=user.id,
            total_price=30.0,
            currency=Currency.EUR,
            status=OrderStatus.CANCELLED_BY_USER,
            expires_at=datetime.datetime.now() + datetime.timedelta(minutes=30)
        )
        session.add_all([order1, order2])
        session.commit()

        # Create invoices for orders
        invoice1 = Invoice(
            order_id=order1.id,
            invoice_number="INV-1234-ABCDEF",
            fiat_amount=50.0,
            fiat_currency=Currency.EUR
        )
        invoice2 = Invoice(
            order_id=order2.id,
            invoice_number="INV-5678-GHIJKL",
            fiat_amount=30.0,
            fiat_currency=Currency.EUR
        )
        session.add_all([invoice1, invoice2])
        session.commit()

        # Create strikes
        strikes = [
            UserStrike(
                user_id=user.id,
                strike_type=StrikeType.TIMEOUT,
                order_id=order1.id,
                reason="Order timed out after 30 minutes",
                created_at=datetime.datetime(2025, 11, 8, 10, 15)
            ),
            UserStrike(
                user_id=user.id,
                strike_type=StrikeType.LATE_CANCEL,
                order_id=order2.id,
                reason="Cancelled after grace period",
                created_at=datetime.datetime(2025, 11, 9, 14, 20)
            ),
            UserStrike(
                user_id=user.id,
                strike_type=StrikeType.TIMEOUT,
                order_id=None,  # No order associated
                reason="Third timeout",
                created_at=datetime.datetime(2025, 11, 10, 15, 30)
            )
        ]
        session.add_all(strikes)
        session.commit()

        return user

    @pytest.mark.asyncio
    async def test_service_returns_dict_not_telegram_objects(self, session, banned_user_with_strikes):
        """Test that service method returns pure data (dict), not Telegram objects."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        # Should return dict, not CallbackQuery or InlineKeyboardBuilder
        assert isinstance(result, dict)
        assert "user_id" in result
        assert "telegram_id" in result
        assert "telegram_username" in result
        assert "strike_count" in result
        assert "strikes" in result

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_user(self, session):
        """Test that service returns None for non-existent user."""
        result = await AdminService.get_banned_user_detail_data(99999, session)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_non_banned_user(self, session):
        """Test that service returns None for non-banned user."""
        user = User(
            telegram_id=123456,
            telegram_username="active_user",
            strike_count=1,
            is_blocked=False
        )
        session.add(user)
        session.commit()

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_user_data(self, session, banned_user_with_strikes):
        """Test that returned data contains correct user information."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        assert result["user_id"] == user.id
        assert result["telegram_id"] == 123456
        assert result["telegram_username"] == "test_user"
        assert result["strike_count"] == 3
        assert result["blocked_at"] == datetime.datetime(2025, 11, 10, 15, 30)
        assert result["blocked_reason"] == "3 strikes reached (automatic ban)"

    @pytest.mark.asyncio
    async def test_returns_all_strikes_sorted_newest_first(self, session, banned_user_with_strikes):
        """Test that strikes are returned sorted by date (newest first)."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        strikes = result["strikes"]
        assert len(strikes) == 3

        # Should be sorted newest first
        assert strikes[0]["created_at"] == datetime.datetime(2025, 11, 10, 15, 30)  # Third strike
        assert strikes[1]["created_at"] == datetime.datetime(2025, 11, 9, 14, 20)   # Second strike
        assert strikes[2]["created_at"] == datetime.datetime(2025, 11, 8, 10, 15)   # First strike

    @pytest.mark.asyncio
    async def test_strike_data_structure(self, session, banned_user_with_strikes):
        """Test that each strike has correct data structure."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        strike = result["strikes"][0]
        assert "created_at" in strike
        assert "strike_type" in strike
        assert "order_invoice_id" in strike
        assert "reason" in strike

        # Check types
        assert isinstance(strike["created_at"], datetime.datetime)
        assert isinstance(strike["strike_type"], str)  # StrikeType enum value
        assert strike["reason"] is None or isinstance(strike["reason"], str)

    @pytest.mark.asyncio
    async def test_strike_includes_invoice_id_when_order_exists(self, session, banned_user_with_strikes):
        """Test that strikes include invoice_id when order is present."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        # Second strike (index 1) has order2 with invoice INV-5678-GHIJKL
        strike_with_order = result["strikes"][1]
        assert strike_with_order["order_invoice_id"] == "INV-5678-GHIJKL"

    @pytest.mark.asyncio
    async def test_strike_has_none_invoice_id_when_no_order(self, session, banned_user_with_strikes):
        """Test that strikes without orders have None for invoice_id."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        # First strike (index 0) has no order
        strike_without_order = result["strikes"][0]
        assert strike_without_order["order_invoice_id"] is None

    @pytest.mark.asyncio
    async def test_limits_to_10_strikes(self, session):
        """Test that method limits strikes to 10 (message length protection)."""
        user = User(
            telegram_id=999999,
            telegram_username="heavy_striker",
            strike_count=15,
            is_blocked=True,
            blocked_at=datetime.datetime.now(),
            blocked_reason="Too many strikes"
        )
        session.add(user)
        session.commit()

        # Create 15 strikes
        for i in range(15):
            strike = UserStrike(
                user_id=user.id,
                strike_type=StrikeType.TIMEOUT,
                order_id=None,
                reason=f"Strike {i+1}",
                created_at=datetime.datetime(2025, 11, 1) + datetime.timedelta(hours=i)
            )
            session.add(strike)
        session.commit()

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        # Should only return 10 strikes
        assert len(result["strikes"]) == 10
        # But total_strike_count should be 15
        assert result["total_strike_count"] == 15

    @pytest.mark.asyncio
    async def test_returns_total_strike_count_for_truncation(self, session, banned_user_with_strikes):
        """Test that total_strike_count is returned for truncation message."""
        user = banned_user_with_strikes

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        assert "total_strike_count" in result
        assert result["total_strike_count"] == 3

    @pytest.mark.asyncio
    async def test_handles_user_without_strikes(self, session):
        """Test that method handles banned user with no strikes."""
        user = User(
            telegram_id=111111,
            telegram_username="no_strikes_user",
            strike_count=0,
            is_blocked=True,
            blocked_at=datetime.datetime.now(),
            blocked_reason="Manual ban by admin"
        )
        session.add(user)
        session.commit()

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        assert result is not None
        assert result["strike_count"] == 0
        assert result["strikes"] == []
        assert result["total_strike_count"] == 0

    @pytest.mark.asyncio
    async def test_handles_user_without_username(self, session):
        """Test that method handles users without telegram_username."""
        user = User(
            telegram_id=222222,
            telegram_username=None,  # No username
            strike_count=1,
            is_blocked=True,
            blocked_at=datetime.datetime.now(),
            blocked_reason="Strike limit reached"
        )
        session.add(user)
        session.commit()

        strike = UserStrike(
            user_id=user.id,
            strike_type=StrikeType.TIMEOUT,
            order_id=None,
            reason="Test strike"
        )
        session.add(strike)
        session.commit()

        result = await AdminService.get_banned_user_detail_data(user.id, session)

        assert result is not None
        assert result["telegram_username"] is None
        assert result["telegram_id"] == 222222


if __name__ == "__main__":
    pytest.main([__file__, "-v"])