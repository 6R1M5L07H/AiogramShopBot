"""
Custom exceptions for AiogramShopBot.

This module provides a hierarchy of custom exceptions for consistent error handling
throughout the application.

Exception Hierarchy:
--------------------
ShopBotException (base)
├── OrderException
│   ├── OrderNotFoundException
│   ├── InsufficientStockException
│   ├── OrderExpiredException
│   ├── OrderAlreadyCancelledException
│   └── InvalidOrderStateException
├── PaymentException
│   ├── PaymentNotFoundException
│   ├── InvalidPaymentAmountException
│   ├── PaymentAlreadyProcessedException
│   └── CryptocurrencyNotSelectedException
├── ItemException
│   ├── ItemNotFoundException
│   ├── ItemAlreadySoldException
│   └── InvalidItemDataException
├── CartException
│   ├── EmptyCartException
│   ├── CartItemNotFoundException
│   └── InvalidCartStateException
├── UserException
│   ├── UserNotFoundException
│   ├── UserBannedException
│   └── InsufficientBalanceException
└── ShippingException
    ├── MissingShippingAddressException
    └── InvalidAddressException

Usage:
------
Services raise specific exceptions:
    raise OrderNotFoundException(order_id=123)

Handlers catch and display user-friendly messages:
    try:
        await OrderService.get_order(order_id)
    except OrderNotFoundException as e:
        await callback.answer(str(e), show_alert=True)
"""

from .base import ShopBotException
from .cart import CartException, EmptyCartException, CartItemNotFoundException, InvalidCartStateException
from .item import ItemException, ItemNotFoundException, ItemAlreadySoldException, InvalidItemDataException
from .order import (
    OrderException,
    OrderNotFoundException,
    InsufficientStockException,
    OrderExpiredException,
    OrderAlreadyCancelledException,
    InvalidOrderStateException
)
from .payment import (
    PaymentException,
    PaymentNotFoundException,
    InvalidPaymentAmountException,
    PaymentAlreadyProcessedException,
    CryptocurrencyNotSelectedException
)
from .shipping import ShippingException, MissingShippingAddressException, InvalidAddressException
from .user import UserException, UserNotFoundException, UserBannedException, InsufficientBalanceException

__all__ = [
    # Base
    'ShopBotException',

    # Cart
    'CartException',
    'EmptyCartException',
    'CartItemNotFoundException',
    'InvalidCartStateException',

    # Item
    'ItemException',
    'ItemNotFoundException',
    'ItemAlreadySoldException',
    'InvalidItemDataException',

    # Order
    'OrderException',
    'OrderNotFoundException',
    'InsufficientStockException',
    'OrderExpiredException',
    'OrderAlreadyCancelledException',
    'InvalidOrderStateException',

    # Payment
    'PaymentException',
    'PaymentNotFoundException',
    'InvalidPaymentAmountException',
    'PaymentAlreadyProcessedException',
    'CryptocurrencyNotSelectedException',

    # Shipping
    'ShippingException',
    'MissingShippingAddressException',
    'InvalidAddressException',

    # User
    'UserException',
    'UserNotFoundException',
    'UserBannedException',
    'InsufficientBalanceException',
]
