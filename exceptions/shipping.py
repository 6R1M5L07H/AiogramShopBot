"""
Shipping-related exceptions.
"""

from .base import ShopBotException


class ShippingException(ShopBotException):
    """Base exception for shipping-related errors."""
    pass


class MissingShippingAddressException(ShippingException):
    """Raised when shipping address required but not provided."""

    def __init__(self, order_id: int):
        super().__init__(
            f"Shipping address required for order {order_id} but not provided",
            details={'order_id': order_id}
        )
        self.order_id = order_id


class InvalidAddressException(ShippingException):
    """Raised when shipping address is invalid or incomplete."""

    def __init__(self, order_id: int, reason: str):
        super().__init__(
            f"Invalid shipping address for order {order_id}: {reason}",
            details={'order_id': order_id, 'reason': reason}
        )
        self.order_id = order_id
        self.reason = reason
