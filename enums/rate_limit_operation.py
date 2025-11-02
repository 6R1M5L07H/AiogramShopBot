from enum import Enum


class RateLimitOperation(str, Enum):
    """
    Rate limit operation types.

    Each operation has its own independent rate limit counter.
    """

    # Order operations
    ORDER_CREATE = "order_create"
    """
    Rate limit for order creation.
    Config: MAX_ORDERS_PER_USER_PER_HOUR
    Default: 5 orders per hour
    """

    # Payment operations
    PAYMENT_CHECK = "payment_check"
    """
    Rate limit for payment status checks.
    Config: MAX_PAYMENT_CHECKS_PER_MINUTE
    Default: 10 checks per minute
    """

    # Wallet operations
    WALLET_TOPUP = "wallet_topup"
    """
    Rate limit for wallet top-up requests.
    Prevents spam of payment address generation.
    """

    # Cart operations
    CART_CHECKOUT = "cart_checkout"
    """
    Rate limit for cart checkout attempts.
    Prevents spam of checkout process.
    """

    # Admin operations
    ANNOUNCEMENT_SEND = "announcement_send"
    """
    Rate limit for admin broadcast announcements.
    Prevents accidental spam to all users.
    """
