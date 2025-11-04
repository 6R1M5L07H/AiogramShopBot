from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean

import config
from enums.cryptocurrency import Cryptocurrency
from enums.currency import Currency
from enums.payment import PaymentType
from models.base import Base


def _get_callback_url() -> str:
    """
    Get callback URL for payment gateway webhooks.

    Uses lazy evaluation to avoid computing URL at import time.
    This ensures config.WEBHOOK_URL is initialized before use.
    """
    if config.WEBHOOK_URL is None:
        raise ValueError(
            "WEBHOOK_URL is not initialized. Call config.initialize_webhook_config() first."
        )
    return f'{config.WEBHOOK_URL}cryptoprocessing/event'


def _get_callback_secret() -> str | None:
    """Get callback secret for payment gateway authentication."""
    secret = config.KRYPTO_EXPRESS_API_SECRET
    return secret if secret and len(secret) > 0 else None


class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    processing_payment_id = Column(Integer, nullable=False)
    topup_reference = Column(String, unique=True, nullable=True)  # TOPUP-YYYY-ABCDEF
    message_id = Column(Integer, nullable=False)
    is_paid = Column(Boolean, nullable=False, default=False)
    expire_datetime = Column(DateTime)


class ProcessingPaymentDTO(BaseModel):
    id: int | None = None
    paymentType: PaymentType = PaymentType.DEPOSIT
    fiatCurrency: Currency
    fiatAmount: float | None = None
    cryptoAmount: float | None = None
    userId: str | None = None
    cryptoCurrency: Cryptocurrency
    expireDatetime: int | None = None
    createDatetime: int | None = None
    address: str | None = None
    isPaid: bool | None = None
    isWithdrawn: bool | None = None
    hash: str | None = None
    callbackUrl: str = Field(default_factory=_get_callback_url)
    callbackSecret: str | None = Field(default_factory=_get_callback_secret)


class DepositRecordDTO(BaseModel):
    """
    Internal database record for deposit (balance top-up) payments.
    Tracks which user created which payment and its status.
    """
    id: int
    user_id: int
    processing_payment_id: int
    topup_reference: str | None = None  # TOPUP-YYYY-ABCDEF
    message_id: int
    is_paid: bool


# Backwards compatibility alias (deprecated)
TablePaymentDTO = DepositRecordDTO
