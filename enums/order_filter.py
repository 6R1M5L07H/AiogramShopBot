from enum import IntEnum


class OrderFilterType(IntEnum):
    """
    Filter types for admin order management.

    Groups orders by status for easier management.
    Default filter: REQUIRES_ACTION (PAID_AWAITING_SHIPMENT)
    """
    # Predefined filter groups
    REQUIRES_ACTION = 1          # PAID_AWAITING_SHIPMENT (DEFAULT - maintains backwards compatibility)
    ALL = 2                      # All orders within retention period
    ACTIVE = 3                   # All active orders (PENDING_*, PAID*, PAID_AWAITING_SHIPMENT)
    COMPLETED = 4                # Completed orders (PAID, SHIPPED)
    CANCELLED = 5                # Cancelled/timeout orders

    # Individual status filters
    PENDING_PAYMENT = 6
    PENDING_PAYMENT_AND_ADDRESS = 7
    PENDING_PAYMENT_PARTIAL = 8
    PAID = 9
    SHIPPED = 10
    CANCELLED_BY_USER = 11
    CANCELLED_BY_ADMIN = 12
    CANCELLED_BY_SYSTEM = 13
    TIMEOUT = 14
