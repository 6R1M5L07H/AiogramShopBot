from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from db import session_execute, session_flush
from models.violation_statistics import ViolationStatistics, ViolationStatisticsDTO


class ViolationStatisticsRepository:
    """Repository for ViolationStatistics model - anonymized violation tracking"""

    @staticmethod
    async def create(violation_dto: ViolationStatisticsDTO, session: AsyncSession | Session) -> int:
        """
        Create new violation statistics record.

        Args:
            violation_dto: Violation data
            session: Database session

        Returns:
            ID of created violation record
        """
        violation = ViolationStatistics(
            violation_date=violation_dto.violation_date.date() if violation_dto.violation_date else datetime.now(timezone.utc).date(),
            violation_type=violation_dto.violation_type,
            order_value=violation_dto.order_value,
            penalty_applied=violation_dto.penalty_applied if violation_dto.penalty_applied is not None else 0.0,
            retry_count=violation_dto.retry_count if violation_dto.retry_count is not None else 0
        )
        session.add(violation)
        await session_flush(session)
        return violation.id

    @staticmethod
    async def get_by_date_range(
        start_date: datetime,
        end_date: datetime,
        session: AsyncSession | Session
    ) -> list[ViolationStatistics]:
        """
        Get violations within date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            session: Database session

        Returns:
            List of ViolationStatistics objects
        """
        stmt = select(ViolationStatistics).where(
            ViolationStatistics.violation_date >= start_date.date(),
            ViolationStatistics.violation_date <= end_date.date()
        ).order_by(ViolationStatistics.violation_date.desc())

        result = await session_execute(stmt, session)
        return result.scalars().all()

    @staticmethod
    async def get_by_type(
        violation_type: str,
        days: int,
        session: AsyncSession | Session
    ) -> list[ViolationStatistics]:
        """
        Get violations of specific type within last N days.

        Args:
            violation_type: Type of violation
            days: Number of days to look back
            session: Database session

        Returns:
            List of ViolationStatistics objects
        """
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(ViolationStatistics).where(
            ViolationStatistics.violation_type == violation_type,
            ViolationStatistics.violation_date >= cutoff_date
        ).order_by(ViolationStatistics.violation_date.desc())

        result = await session_execute(stmt, session)
        return result.scalars().all()

    @staticmethod
    async def get_violation_count_by_type(
        violation_type: str,
        days: int,
        session: AsyncSession | Session
    ) -> int:
        """
        Get count of violations of specific type for last N days.

        Args:
            violation_type: Type of violation
            days: Number of days to look back
            session: Database session

        Returns:
            Count of violations
        """
        violations = await ViolationStatisticsRepository.get_by_type(violation_type, days, session)
        return len(violations)

    @staticmethod
    async def get_violation_count(
        days: int,
        session: AsyncSession | Session
    ) -> dict[str, int]:
        """
        Get violation counts by type for last N days.

        Args:
            days: Number of days to look back
            session: Database session

        Returns:
            Dictionary mapping violation_type to count
        """
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(ViolationStatistics).where(
            ViolationStatistics.violation_date >= cutoff_date
        )

        result = await session_execute(stmt, session)
        violations = result.scalars().all()

        # Count by type
        counts = {}
        for violation in violations:
            counts[violation.violation_type] = counts.get(violation.violation_type, 0) + 1

        return counts

    @staticmethod
    async def get_total_penalty_amount(
        days: int,
        session: AsyncSession | Session
    ) -> float:
        """
        Get total penalties collected for last N days.

        Args:
            days: Number of days to look back
            session: Database session

        Returns:
            Total penalty amount
        """
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(ViolationStatistics).where(
            ViolationStatistics.violation_date >= cutoff_date
        )

        result = await session_execute(stmt, session)
        violations = result.scalars().all()

        return sum(v.penalty_applied for v in violations)

    # Alias for backwards compatibility with tests
    get_total_penalties = get_total_penalty_amount