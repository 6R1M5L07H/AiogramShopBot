"""
Unit tests for ViolationStatisticsRepository

Tests CRUD operations for anonymized violation statistics using in-memory SQLite database.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.violation_statistics import ViolationStatistics, ViolationStatisticsDTO
from repositories.violation_statistics import ViolationStatisticsRepository
from enums.violation_type import ViolationType


class TestViolationStatisticsRepository:
    """Test ViolationStatisticsRepository CRUD operations."""

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

    @pytest.mark.asyncio
    async def test_create_success(self, session):
        """Test successful creation of ViolationStatistics."""
        # Arrange
        now = datetime.now(timezone.utc)

        dto = ViolationStatisticsDTO(
            violation_date=now,
            violation_type=ViolationType.UNDERPAYMENT_FINAL,
            order_value=100.0,
            penalty_applied=5.0,
            retry_count=1
        )

        # Act
        result = await ViolationStatisticsRepository.create(dto, session)
        session.commit()

        # Assert
        assert isinstance(result, int)

        # Verify record was created
        record = session.query(ViolationStatistics).filter_by(id=result).first()
        assert record is not None
        assert record.violation_type == ViolationType.UNDERPAYMENT_FINAL
        assert record.order_value == 100.0
        assert record.penalty_applied == 5.0

    @pytest.mark.asyncio
    async def test_get_by_type(self, session):
        """Test retrieval of violations by type."""
        # Arrange
        now = datetime.now(timezone.utc)

        # Create late payment violations
        dto1 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=5),
            violation_type=ViolationType.LATE_PAYMENT,
            order_value=100.0,
            penalty_applied=5.0,
            retry_count=0
        )

        dto2 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=10),
            violation_type=ViolationType.LATE_PAYMENT,
            order_value=150.0,
            penalty_applied=7.5,
            retry_count=0
        )

        # Create timeout violation (different type)
        dto3 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=3),
            violation_type=ViolationType.TIMEOUT,
            order_value=75.0,
            penalty_applied=0.0,
            retry_count=0
        )

        await ViolationStatisticsRepository.create(dto1, session)
        await ViolationStatisticsRepository.create(dto2, session)
        await ViolationStatisticsRepository.create(dto3, session)
        session.commit()

        # Act
        result = await ViolationStatisticsRepository.get_by_type(
            ViolationType.LATE_PAYMENT, 30, session
        )

        # Assert
        assert len(result) == 2
        assert all(v.violation_type == ViolationType.LATE_PAYMENT for v in result)

    @pytest.mark.asyncio
    async def test_get_by_type_no_violations(self, session):
        """Test get_by_type when no violations exist."""
        # Act
        result = await ViolationStatisticsRepository.get_by_type(
            ViolationType.TIMEOUT, 30, session
        )

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_total_penalties(self, session):
        """Test retrieval of total penalty amount."""
        # Arrange
        now = datetime.now(timezone.utc)

        dto1 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=5),
            violation_type=ViolationType.LATE_PAYMENT,
            order_value=100.0,
            penalty_applied=5.0,
            retry_count=0
        )

        dto2 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=10),
            violation_type=ViolationType.UNDERPAYMENT_FINAL,
            order_value=200.0,
            penalty_applied=10.0,
            retry_count=1
        )

        dto3 = ViolationStatisticsDTO(
            violation_date=now - timedelta(days=40),  # Outside 30 days
            violation_type=ViolationType.LATE_PAYMENT,
            order_value=150.0,
            penalty_applied=7.5,
            retry_count=0
        )

        await ViolationStatisticsRepository.create(dto1, session)
        await ViolationStatisticsRepository.create(dto2, session)
        await ViolationStatisticsRepository.create(dto3, session)
        session.commit()

        # Act
        result = await ViolationStatisticsRepository.get_total_penalties(30, session)

        # Assert
        assert result == 15.0  # 5.0 + 10.0, excluding the one from 40 days ago

    @pytest.mark.asyncio
    async def test_get_total_penalties_no_penalties(self, session):
        """Test total penalties when no violations exist."""
        # Act
        result = await ViolationStatisticsRepository.get_total_penalties(30, session)

        # Assert
        assert result == 0.0
