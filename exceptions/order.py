"""
Order-related exceptions.
"""

from .base import ShopBotException


class OrderException(ShopBotException):
    """Base exception for order-related errors."""
    pass


class OrderNotFoundException(OrderException):
    """Raised when order is not found in database."""

    def __init__(self, order_id: int):
        super().__init__(
            f"Order {order_id} not found",
            details={'order_id': order_id}
        )
        self.order_id = order_id


class InsufficientStockException(OrderException):
    """Raised when trying to reserve items with insufficient stock."""

    def __init__(self, item_id: int, requested: int, available: int):
        super().__init__(
            f"Insufficient stock for item {item_id}: requested {requested}, available {available}",
            details={'item_id': item_id, 'requested': requested, 'available': available}
        )
        self.item_id = item_id
        self.requested = requested
        self.available = available


class OrderExpiredException(OrderException):
    """Raised when trying to process an expired order."""

    def __init__(self, order_id: int):
        super().__init__(
            f"Order {order_id} has expired",
            details={'order_id': order_id}
        )
        self.order_id = order_id


class OrderAlreadyCancelledException(OrderException):
    """Raised when trying to cancel an already cancelled order."""

    def __init__(self, order_id: int):
        super().__init__(
            f"Order {order_id} is already cancelled",
            details={'order_id': order_id}
        )
        self.order_id = order_id


class InvalidOrderStateException(OrderException):
    """Raised when order is in invalid state for requested operation."""

    def __init__(self, order_id: int, current_state: str, required_state: str):
        super().__init__(
            f"Order {order_id} is in state '{current_state}', required '{required_state}'",
            details={'order_id': order_id, 'current_state': current_state, 'required_state': required_state}
        )
        self.order_id = order_id
        self.current_state = current_state
        self.required_state = required_state


class OrderOwnershipException(OrderException):
    """Raised when user attempts to access/modify order they don't own."""

    def __init__(self, order_id: int, user_id: int):
        super().__init__(
            f"User {user_id} does not have permission to access order {order_id}",
            details={'order_id': order_id, 'user_id': user_id}
        )
        self.order_id = order_id
        self.user_id = user_id
