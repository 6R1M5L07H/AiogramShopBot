from enum import Enum


class OrderStatus(Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"                   # Waiting for payment
    PENDING_PAYMENT_PARTIAL = "PENDING_PAYMENT_PARTIAL"   # After 1st underpayment (30 min extension)
    PAID = "PAID"                                         # Paid successfully
    SHIPPED = "SHIPPED"                                   # Shipped (optional for admin)
    CANCELLED_BY_USER = "CANCELLED_BY_USER"               # Cancelled by user (after grace period → strike!)
    CANCELLED_BY_ADMIN = "CANCELLED_BY_ADMIN"             # Cancelled by admin (no strike)
    TIMEOUT = "TIMEOUT"                                   # Timeout expired (includes underpayment failures)