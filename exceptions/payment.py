"""
Payment-related exceptions.
"""

from .base import ShopBotException


class PaymentException(ShopBotException):
    """Base exception for payment-related errors."""
    pass


class PaymentNotFoundException(PaymentException):
    """Raised when payment/invoice is not found."""

    def __init__(self, invoice_id: int | None = None, order_id: int | None = None):
        if invoice_id:
            message = f"Payment/Invoice {invoice_id} not found"
            details = {'invoice_id': invoice_id}
        elif order_id:
            message = f"Payment/Invoice for order {order_id} not found"
            details = {'order_id': order_id}
        else:
            message = "Payment/Invoice not found"
            details = {}

        super().__init__(message, details)
        self.invoice_id = invoice_id
        self.order_id = order_id


class InvalidPaymentAmountException(PaymentException):
    """Raised when payment amount is invalid."""

    def __init__(self, expected: float, received: float, currency: str):
        super().__init__(
            f"Invalid payment amount: expected {expected} {currency}, received {received} {currency}",
            details={'expected': expected, 'received': received, 'currency': currency}
        )
        self.expected = expected
        self.received = received
        self.currency = currency


class PaymentAlreadyProcessedException(PaymentException):
    """Raised when trying to process an already completed payment."""

    def __init__(self, invoice_id: int):
        super().__init__(
            f"Payment/Invoice {invoice_id} already processed",
            details={'invoice_id': invoice_id}
        )
        self.invoice_id = invoice_id


class CryptocurrencyNotSelectedException(PaymentException):
    """Raised when cryptocurrency not selected but payment requires it."""

    def __init__(self, order_id: int):
        super().__init__(
            f"Cryptocurrency not selected for order {order_id}",
            details={'order_id': order_id}
        )
        self.order_id = order_id
