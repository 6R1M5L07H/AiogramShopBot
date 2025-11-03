"""
Cart-related exceptions.
"""

from .base import ShopBotException


class CartException(ShopBotException):
    """Base exception for cart-related errors."""
    pass


class EmptyCartException(CartException):
    """Raised when trying to checkout with empty cart."""

    def __init__(self, user_id: int):
        super().__init__(
            f"Cart is empty for user {user_id}",
            details={'user_id': user_id}
        )
        self.user_id = user_id


class CartItemNotFoundException(CartException):
    """Raised when cart item not found."""

    def __init__(self, cart_item_id: int):
        super().__init__(
            f"Cart item {cart_item_id} not found",
            details={'cart_item_id': cart_item_id}
        )
        self.cart_item_id = cart_item_id


class InvalidCartStateException(CartException):
    """Raised when cart is in invalid state for operation."""

    def __init__(self, user_id: int, reason: str):
        super().__init__(
            f"Invalid cart state for user {user_id}: {reason}",
            details={'user_id': user_id, 'reason': reason}
        )
        self.user_id = user_id
        self.reason = reason
