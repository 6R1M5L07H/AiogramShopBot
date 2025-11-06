"""
User-related exceptions.
"""

from .base import ShopBotException


class UserException(ShopBotException):
    """Base exception for user-related errors."""
    pass


class UserNotFoundException(UserException):
    """Raised when user is not found in database."""

    def __init__(self, user_id: int | None = None, telegram_id: int | None = None):
        if user_id:
            message = f"User with ID {user_id} not found"
            details = {'user_id': user_id}
        elif telegram_id:
            message = f"User with Telegram ID {telegram_id} not found"
            details = {'telegram_id': telegram_id}
        else:
            message = "User not found"
            details = {}

        super().__init__(message, details)
        self.user_id = user_id
        self.telegram_id = telegram_id


class UserBannedException(UserException):
    """Raised when banned user tries to perform action."""

    def __init__(self, telegram_id: int, reason: str | None = None):
        message = f"User {telegram_id} is banned"
        if reason:
            message += f": {reason}"

        super().__init__(
            message,
            details={'telegram_id': telegram_id, 'reason': reason}
        )
        self.telegram_id = telegram_id
        self.reason = reason


class InsufficientBalanceException(UserException):
    """Raised when user has insufficient wallet balance."""

    def __init__(self, user_id: int, required: float, available: float):
        super().__init__(
            f"Insufficient balance for user {user_id}: required {required}, available {available}",
            details={'user_id': user_id, 'required': required, 'available': available}
        )
        self.user_id = user_id
        self.required = required
        self.available = available
