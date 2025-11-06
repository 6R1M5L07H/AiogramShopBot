"""
Error Handler Utility for Telegram Bot Handlers

Provides centralized error handling for bot handlers with:
- Localized error messages
- Consistent user experience
- Automatic exception to message mapping
- Logging for debugging

Usage in handlers:
    from utils.error_handler import handle_service_error

    try:
        result = await SomeService.some_method()
    except ShopBotException as e:
        error_message = handle_service_error(e)
        await callback.answer(error_message, show_alert=True)
"""

import logging
from typing import Optional

from enums.bot_entity import BotEntity
from exceptions import (
    ShopBotException,
    OrderNotFoundException,
    OrderExpiredException,
    OrderAlreadyCancelledException,
    InvalidOrderStateException,
    InsufficientStockException,
    PaymentNotFoundException,
    InvalidPaymentAmountException,
    PaymentAlreadyProcessedException,
    CryptocurrencyNotSelectedException,
    ItemNotFoundException,
    ItemAlreadySoldException,
    InvalidItemDataException,
    EmptyCartException,
    CartItemNotFoundException,
    InvalidCartStateException,
    UserNotFoundException,
    UserBannedException,
    InsufficientBalanceException,
    MissingShippingAddressException,
    InvalidAddressException,
)
from utils.localizator import Localizator


def handle_service_error(exception: ShopBotException, entity: BotEntity = BotEntity.ADMIN) -> str:
    """
    Convert service exception to localized user-friendly error message.

    Args:
        exception: The custom exception raised by a service
        entity: Bot entity for localization (ADMIN or USER)

    Returns:
        Localized error message string

    Example:
        try:
            order = await OrderService.get_order(123)
        except OrderNotFoundException as e:
            message = handle_service_error(e, BotEntity.USER)
            await callback.answer(message, show_alert=True)
    """
    # Log the error for debugging
    logging.warning(f"Service error handled: {type(exception).__name__} - {str(exception)}")

    # Map exception types to localization keys
    error_mapping = {
        # Order exceptions
        OrderNotFoundException: "error_order_not_found",
        OrderExpiredException: "error_order_expired",
        OrderAlreadyCancelledException: "error_order_already_cancelled",
        InvalidOrderStateException: "error_order_invalid_state",
        InsufficientStockException: "error_insufficient_stock",

        # Payment exceptions
        PaymentNotFoundException: "error_payment_not_found",
        InvalidPaymentAmountException: "error_invalid_payment_amount",
        PaymentAlreadyProcessedException: "error_payment_already_processed",
        CryptocurrencyNotSelectedException: "error_crypto_not_selected",

        # Item exceptions
        ItemNotFoundException: "error_item_not_found",
        ItemAlreadySoldException: "error_item_already_sold",
        InvalidItemDataException: "error_invalid_item_data",

        # Cart exceptions
        EmptyCartException: "error_empty_cart",
        CartItemNotFoundException: "error_cart_item_not_found",
        InvalidCartStateException: "error_invalid_cart_state",

        # User exceptions
        UserNotFoundException: "error_user_not_found",
        UserBannedException: "error_user_banned",
        InsufficientBalanceException: "error_insufficient_balance",

        # Shipping exceptions
        MissingShippingAddressException: "error_missing_shipping_address",
        InvalidAddressException: "error_invalid_address",
    }

    # Get localization key for this exception type
    localization_key = error_mapping.get(type(exception))

    if not localization_key:
        # Unknown exception type - use generic error message
        logging.error(f"Unmapped exception type: {type(exception).__name__}")
        return Localizator.get_text(entity, "error_unexpected")

    # Get exception attributes for formatting
    exception_data = {}

    # Extract common attributes from exceptions
    if hasattr(exception, 'order_id'):
        exception_data['order_id'] = exception.order_id
    if hasattr(exception, 'current_state'):
        exception_data['current_state'] = exception.current_state
    if hasattr(exception, 'required_state'):
        exception_data['required_state'] = exception.required_state
    if hasattr(exception, 'available'):
        exception_data['available'] = exception.available
    if hasattr(exception, 'requested'):
        exception_data['requested'] = exception.requested
    if hasattr(exception, 'details'):
        exception_data['details'] = exception.details
    if hasattr(exception, 'reason'):
        exception_data['reason'] = exception.reason
    if hasattr(exception, 'required'):
        exception_data['required'] = exception.required

    # Get localized message with formatting
    try:
        return Localizator.get_text(entity, localization_key).format(**exception_data)
    except KeyError as e:
        # Missing formatting parameter - log and return without formatting
        logging.error(f"Missing format parameter in error message: {e}")
        return Localizator.get_text(entity, localization_key)


def handle_unexpected_error(exception: Exception, entity: BotEntity = BotEntity.ADMIN) -> str:
    """
    Handle unexpected exceptions (non-ShopBotException).

    Args:
        exception: Any exception
        entity: Bot entity for localization

    Returns:
        Generic error message

    Note:
        Also logs the full exception for debugging
    """
    logging.error(f"Unexpected error: {type(exception).__name__} - {str(exception)}", exc_info=True)
    return Localizator.get_text(entity, "error_unexpected")


def safe_service_call(entity: BotEntity = BotEntity.ADMIN):
    """
    Decorator for handlers to automatically catch and handle service exceptions.

    Usage:
        @safe_service_call(BotEntity.USER)
        async def my_handler(callback: CallbackQuery, **kwargs):
            # Service calls here - exceptions automatically handled
            result = await OrderService.get_order(123)
            ...

    Note:
        Handler must accept **kwargs and have 'callback' parameter
    """
    def decorator(handler_func):
        async def wrapper(*args, **kwargs):
            # Try to get callback from kwargs first, then check positional args
            callback = kwargs.get('callback')
            if not callback and args:
                # Check if first positional arg is a CallbackQuery
                from aiogram.types import CallbackQuery
                if isinstance(args[0], CallbackQuery):
                    callback = args[0]

            if not callback:
                # Can't send error message without callback
                logging.error("safe_service_call: No callback found in args or kwargs")
                return await handler_func(*args, **kwargs)

            try:
                return await handler_func(*args, **kwargs)
            except ShopBotException as e:
                error_message = handle_service_error(e, entity)
                await callback.answer(error_message, show_alert=True)
            except Exception as e:
                error_message = handle_unexpected_error(e, entity)
                await callback.answer(error_message, show_alert=True)

        return wrapper
    return decorator
