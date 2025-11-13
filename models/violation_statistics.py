from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Float, Date, DateTime, func, Enum as SQLEnum

from models.base import Base
from enums.violation_type import ViolationType


class ViolationStatistics(Base):
    """
    Anonymized violation tracking for abuse pattern analysis.

    NO user identification - only counts, types, and financial impact.
    Data minimization - cannot link violations to specific users.

    Used for:
    - Abuse pattern detection (e.g., high underpayment rate on specific days)
    - Financial loss tracking
    - System health monitoring
    """
    __tablename__ = 'violation_statistics'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === Temporal Data ===
    violation_date = Column(Date, nullable=False, index=True)

    # === Violation Type ===
    violation_type = Column(SQLEnum(ViolationType), nullable=False, index=True)

    # === Financial Impact ===
    order_value = Column(Float, nullable=False)  # What was the order worth?
    penalty_applied = Column(Float, nullable=False, default=0.0)  # Penalty amount (if any)

    # === Retry Information (for underpayments) ===
    retry_count = Column(Integer, nullable=False, default=0)  # 0, 1, or 2

    # === Metadata ===
    created_at = Column(DateTime, default=func.now())


class ViolationStatisticsDTO(BaseModel):
    """DTO for ViolationStatistics creation"""
    id: int | None = None
    violation_date: datetime | None = None  # Will be converted to Date
    violation_type: ViolationType | None = None
    order_value: float | None = None
    penalty_applied: float | None = None
    retry_count: int | None = None
    created_at: datetime | None = None
