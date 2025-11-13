from enum import Enum


class ViolationType(str, Enum):
    """Types of order violations for anonymized statistics tracking"""

    # Payment violations
    UNDERPAYMENT_FINAL = "underpayment_final"  # Second underpayment, order cancelled
    LATE_PAYMENT = "late_payment"  # Payment received after timeout

    # Cancellation violations
    USER_CANCELLATION_LATE = "user_cancellation_late"  # User cancelled outside grace period (strike)
    TIMEOUT = "timeout"  # Order timed out (no payment)