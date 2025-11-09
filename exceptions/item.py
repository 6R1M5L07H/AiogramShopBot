"""
Item-related exceptions.
"""

from .base import ShopBotException


class ItemException(ShopBotException):
    """Base exception for item-related errors."""
    pass


class ItemNotFoundException(ItemException):
    """Raised when item is not found in database."""

    def __init__(self, item_id: int | None = None, category_id: int | None = None, subcategory_id: int | None = None):
        if item_id:
            message = f"Item {item_id} not found"
            details = {'item_id': item_id}
        elif category_id and subcategory_id:
            message = f"No items found for category {category_id}, subcategory {subcategory_id}"
            details = {'category_id': category_id, 'subcategory_id': subcategory_id}
        else:
            message = "Item not found"
            details = {}

        super().__init__(message, details)
        self.item_id = item_id
        self.category_id = category_id
        self.subcategory_id = subcategory_id


class ItemAlreadySoldException(ItemException):
    """Raised when trying to purchase already sold item."""

    def __init__(self, item_id: int):
        super().__init__(
            f"Item {item_id} is already sold",
            details={'item_id': item_id}
        )
        self.item_id = item_id


class InvalidItemDataException(ItemException):
    """Raised when item data is invalid or corrupted."""

    def __init__(self, item_id: int, reason: str):
        super().__init__(
            f"Invalid data for item {item_id}: {reason}",
            details={'item_id': item_id, 'reason': reason}
        )
        self.item_id = item_id
        self.reason = reason


class TierPricingCalculationException(ItemException):
    """Raised when tier pricing calculation fails."""

    def __init__(self, subcategory_id: int, quantity: int, reason: str):
        super().__init__(
            f"Tier pricing calculation failed for subcategory {subcategory_id} (qty: {quantity}): {reason}",
            details={'subcategory_id': subcategory_id, 'quantity': quantity, 'reason': reason}
        )
        self.subcategory_id = subcategory_id
        self.quantity = quantity
        self.reason = reason
