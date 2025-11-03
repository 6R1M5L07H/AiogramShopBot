"""
Base exception classes for AiogramShopBot.
"""


class ShopBotException(Exception):
    """
    Base exception for all shop bot errors.

    All custom exceptions in the bot should inherit from this class.
    This allows catching all bot-specific exceptions with a single handler.

    Attributes:
        message: Human-readable error message
        details: Optional dict with additional context (entity IDs, states, etc.)
    """

    def __init__(self, message: str, details: dict | None = None):
        """
        Initialize base exception.

        Args:
            message: Human-readable error message
            details: Optional dict with additional context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return the error message."""
        return self.message

    def __repr__(self) -> str:
        """Return detailed representation with context."""
        if self.details:
            details_str = ', '.join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.__class__.__name__}('{self.message}', {details_str})"
        return f"{self.__class__.__name__}('{self.message}')"
