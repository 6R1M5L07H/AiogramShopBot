"""
Order Filter Utilities

Maps OrderFilterType enum to lists of OrderStatus for database queries.
"""
from enums.order_filter import OrderFilterType
from enums.order_status import OrderStatus


def get_status_filter_for_filter_type(filter_type: OrderFilterType | int | None) -> list[OrderStatus] | None:
    """
    Converts OrderFilterType to list of OrderStatus values for repository queries.

    Args:
        filter_type: OrderFilterType enum value (or None for default)

    Returns:
        List of OrderStatus to filter by, or None for all orders

    Default behavior:
        None or REQUIRES_ACTION → [PAID_AWAITING_SHIPMENT]
        This maintains backwards compatibility with existing shipping management.
    """
    # Handle None or default
    if filter_type is None or filter_type == OrderFilterType.REQUIRES_ACTION:
        return [OrderStatus.PAID_AWAITING_SHIPMENT]

    # Filter groups
    if filter_type == OrderFilterType.ALL:
        return None  # No filter = all orders

    if filter_type == OrderFilterType.ACTIVE:
        # ACTIVE = Orders requiring action (payment pending or shipment needed)
        # Excludes PAID (digital orders are complete, nothing to do)
        return [
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
            OrderStatus.PENDING_PAYMENT_PARTIAL,
            OrderStatus.PAID_AWAITING_SHIPMENT
        ]

    if filter_type == OrderFilterType.COMPLETED:
        return [OrderStatus.PAID, OrderStatus.SHIPPED]

    if filter_type == OrderFilterType.CANCELLED:
        return [
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.TIMEOUT
        ]

    # Individual status filters
    if filter_type == OrderFilterType.PENDING_PAYMENT:
        return [OrderStatus.PENDING_PAYMENT]

    if filter_type == OrderFilterType.PENDING_PAYMENT_AND_ADDRESS:
        return [OrderStatus.PENDING_PAYMENT_AND_ADDRESS]

    if filter_type == OrderFilterType.PENDING_PAYMENT_PARTIAL:
        return [OrderStatus.PENDING_PAYMENT_PARTIAL]

    if filter_type == OrderFilterType.PAID:
        return [OrderStatus.PAID]

    if filter_type == OrderFilterType.SHIPPED:
        return [OrderStatus.SHIPPED]

    if filter_type == OrderFilterType.CANCELLED_BY_USER:
        return [OrderStatus.CANCELLED_BY_USER]

    if filter_type == OrderFilterType.CANCELLED_BY_ADMIN:
        return [OrderStatus.CANCELLED_BY_ADMIN]

    if filter_type == OrderFilterType.CANCELLED_BY_SYSTEM:
        return [OrderStatus.CANCELLED_BY_SYSTEM]

    if filter_type == OrderFilterType.TIMEOUT:
        return [OrderStatus.TIMEOUT]

    # Fallback: default filter
    return [OrderStatus.PAID_AWAITING_SHIPMENT]


def get_status_filter_for_user(filter_type: OrderFilterType | int | None) -> list[OrderStatus] | None:
    """
    Converts OrderFilterType to list of OrderStatus values for user order history queries.

    User-specific behavior:
        None → ALL non-pending orders (PAID, SHIPPED, CANCELLED_*)
        COMPLETED → PAID + SHIPPED
        CANCELLED → All cancelled states

    Args:
        filter_type: OrderFilterType enum value (or None for ALL)

    Returns:
        List of OrderStatus to filter by
    """
    # User sees only completed/cancelled orders (no pending orders in history)
    if filter_type is None:
        # ALL = Show all non-pending orders (including awaiting shipment)
        return [
            OrderStatus.PAID,
            OrderStatus.PAID_AWAITING_SHIPMENT,
            OrderStatus.SHIPPED,
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.TIMEOUT,
        ]

    if filter_type == OrderFilterType.COMPLETED:
        return [OrderStatus.PAID, OrderStatus.PAID_AWAITING_SHIPMENT, OrderStatus.SHIPPED]

    if filter_type == OrderFilterType.CANCELLED:
        return [
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.TIMEOUT,
        ]

    # Fallback to all non-pending
    return [
        OrderStatus.PAID,
        OrderStatus.PAID_AWAITING_SHIPMENT,
        OrderStatus.SHIPPED,
        OrderStatus.CANCELLED_BY_USER,
        OrderStatus.CANCELLED_BY_ADMIN,
        OrderStatus.CANCELLED_BY_SYSTEM,
        OrderStatus.TIMEOUT,
    ]
