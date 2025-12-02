from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, String, Boolean, Float, func, CheckConstraint
from sqlalchemy import Enum as SQLEnum

from enums.approval_status import ApprovalStatus
from models.base import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_username = Column(String, unique=True)
    telegram_id = Column(Integer, nullable=False, unique=True)
    registered_at = Column(DateTime, default=func.now())
    can_receive_messages = Column(Boolean, default=True)

    # Strike-System
    strike_count = Column(Integer, nullable=False, default=0)
    is_blocked = Column(Boolean, nullable=False, default=False)
    blocked_at = Column(DateTime, nullable=True)
    blocked_reason = Column(String, nullable=True)

    # Wallet-System (Fiat-based for MVP)
    top_up_amount = Column(Float, nullable=False, default=0.0)

    # Registration Management System
    approval_status = Column(SQLEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.APPROVED)
    approval_requested_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_admin_id = Column(Integer, nullable=True)
    rejection_reason = Column(String, nullable=True)

    # User Statistics (DUMMY values - TODO: Implement Trust-Level System)
    # These fields are placeholders for future trust-level/reputation system
    # Currently always return DUMMY values (0.0, 0, NULL)
    lifetime_revenue = Column(Float, nullable=False, default=0.0)  # DUMMY: Always 0.0
    lifetime_orders = Column(Integer, nullable=False, default=0)   # DUMMY: Always 0
    first_order_date = Column(DateTime, nullable=True)             # DUMMY: Always NULL
    last_order_date = Column(DateTime, nullable=True)              # DUMMY: Always NULL

    # Referral-System (preparation for future feature)
    referral_code = Column(String(8), unique=True, nullable=True)
    referral_code_created_at = Column(DateTime, nullable=True)
    successful_orders_count = Column(Integer, nullable=False, default=0)
    referral_eligible = Column(Boolean, nullable=False, default=False)
    max_referrals = Column(Integer, nullable=False, default=10)
    successful_referrals_count = Column(Integer, nullable=False, default=0)
    referred_by_user_id = Column(Integer, nullable=True)
    referred_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint('strike_count >= 0', name='check_strike_count_positive'),
        CheckConstraint('top_up_amount >= 0', name='check_wallet_balance_positive'),
        CheckConstraint('successful_orders_count >= 0', name='check_orders_count_positive'),
        CheckConstraint('max_referrals >= 0', name='check_max_referrals_positive'),
        CheckConstraint('successful_referrals_count >= 0', name='check_referrals_count_positive'),
        CheckConstraint('lifetime_revenue >= 0', name='check_lifetime_revenue_positive'),
        CheckConstraint('lifetime_orders >= 0', name='check_lifetime_orders_positive'),
    )


class UserDTO(BaseModel):
    id: int | None = None
    telegram_username: str | None = None
    telegram_id: int | None = None
    registered_at: datetime | None = None
    can_receive_messages: bool | None = None
    strike_count: int | None = None
    is_blocked: bool | None = None
    blocked_at: datetime | None = None
    blocked_reason: str | None = None
    top_up_amount: float | None = None
    referral_code: str | None = None
    referral_code_created_at: datetime | None = None
    successful_orders_count: int | None = None
    referral_eligible: bool | None = None
    max_referrals: int | None = None
    successful_referrals_count: int | None = None
    referred_by_user_id: int | None = None
    referred_at: datetime | None = None

    # Registration Management System
    approval_status: ApprovalStatus | None = None
    approval_requested_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by_admin_id: int | None = None
    rejection_reason: str | None = None

    # User Statistics (DUMMY values)
    lifetime_revenue: float | None = None
    lifetime_orders: int | None = None
    first_order_date: datetime | None = None
    last_order_date: datetime | None = None
