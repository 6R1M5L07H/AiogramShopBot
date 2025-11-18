"""
API router for WebApp data submission.

Handles encrypted shipping address submissions from Telegram Mini Apps
via HTTP POST (required for InlineKeyboard WebApps, as sendData() only
works with ReplyKeyboard buttons).

Security:
- Validates Telegram WebApp initData HMAC signature
- Rate limiting per user
- Order ownership verification
"""

import logging
import json
import uuid
import traceback
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal

import config
from db import get_db_session
from utils.telegram_webapp_validator import (
    validate_telegram_webapp_init_data,
    extract_user_id,
    WebAppValidationError
)
from services.shipping import ShippingService
from services.notification import NotificationService
from exceptions.order import (
    OrderNotFoundException,
    OrderOwnershipException,
    InvalidOrderStateException
)
from enums.bot_entity import BotEntity
from utils.localizator import Localizator

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api", tags=["api"])


def generate_correlation_id() -> str:
    """Generate unique correlation ID for request tracing."""
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


class EncryptedAddressPayload(BaseModel):
    """Payload for encrypted shipping address submission."""
    order_id: int = Field(..., gt=0, description="Order ID")
    encrypted_address: str = Field(..., min_length=100, max_length=10000, description="PGP encrypted address")
    encryption_mode: Literal["pgp", "aes"] = Field(..., description="Encryption mode used")


@api_router.post("/shipping/address")
async def submit_encrypted_address(request: Request, payload: EncryptedAddressPayload):
    """
    Submit encrypted shipping address from Telegram Mini App.

    This endpoint receives PGP-encrypted shipping addresses from the Mini App
    running inside Telegram. The Mini App opens via InlineKeyboard button,
    which cannot use Telegram.WebApp.sendData() (only works with ReplyKeyboard).

    Security:
    - Validates Telegram WebApp initData HMAC signature
    - Verifies user owns the order
    - Checks order status (one-time submission only)
    - Updates order status to PENDING_PAYMENT after success
    - Sends payment message to bot

    Request Headers:
        X-Telegram-Init-Data: Telegram WebApp initData with HMAC signature

    Request Body:
        {
            "order_id": 123,
            "encrypted_address": "-----BEGIN PGP MESSAGE-----...",
            "encryption_mode": "pgp"
        }

    Returns:
        200: Address saved successfully, order ready for payment
        400: Invalid request data
        401: Unauthorized (invalid signature or user doesn't own order)
        404: Order not found
        409: Order status doesn't allow address changes
        500: Server error

    Example:
        curl -X POST https://bot.com/api/shipping/address \\
          -H "Content-Type: application/json" \\
          -H "X-Telegram-Init-Data: query_id=...&user=...&hash=..." \\
          -d '{"order_id":123,"encrypted_address":"-----BEGIN PGP...","encryption_mode":"pgp"}'
    """
    correlation_id = generate_correlation_id()
    logger.info(f"[{correlation_id}] Processing address submission for order {payload.order_id}")

    # Extract initData from header
    init_data = request.headers.get('X-Telegram-Init-Data')
    if not init_data:
        logger.warning(f"[{correlation_id}] Missing X-Telegram-Init-Data header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=Localizator.get_text(BotEntity.USER, "unauthorized_error")
        )

    # Validate Telegram WebApp signature
    try:
        validated_data = validate_telegram_webapp_init_data(
            init_data=init_data,
            bot_token=config.TOKEN,
            max_age_seconds=3600  # 1 hour
        )
        user_id = extract_user_id(validated_data)
        logger.info(f"[{correlation_id}] ✅ Validated WebApp request from user {user_id}")
    except WebAppValidationError as e:
        logger.warning(f"[{correlation_id}] WebApp validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=Localizator.get_text(BotEntity.USER, "unauthorized_error")
        )

    # Save encrypted address via service layer
    async with get_db_session() as session:
        try:
            await ShippingService.save_encrypted_shipping_address(
                order_id=payload.order_id,
                encrypted_address=payload.encrypted_address,
                encryption_mode=payload.encryption_mode,
                user_id=user_id,
                session=session
            )

            logger.info(
                f"[{correlation_id}] ✅ Saved {payload.encryption_mode.upper()} encrypted address "
                f"for order {payload.order_id} (user {user_id}, {len(payload.encrypted_address)} bytes)"
            )

            # Send payment message to bot
            from bot_instance import get_bot
            from callbacks import OrderCallback
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            bot = get_bot()

            # Build continue button (goes to shipping upsell, then payment)
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "proceed_to_payment"),
                callback_data=OrderCallback.create(level=7, order_id=payload.order_id)
            )

            # Send success message with continue prompt
            await bot.send_message(
                user_id,
                text=Localizator.get_text(BotEntity.USER, "address_encrypted_success"),
                reply_markup=kb_builder.as_markup()
            )

            logger.info(f"[{correlation_id}] ✅ Payment message sent to user {user_id}")

            return {
                "success": True,
                "message": "Address saved successfully",
                "order_id": payload.order_id
            }

        except OrderNotFoundException:
            logger.warning(f"[{correlation_id}] Order {payload.order_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Localizator.get_text(BotEntity.USER, "order_not_found_error")
            )

        except OrderOwnershipException as e:
            logger.error(f"[{correlation_id}] Ownership violation", exc_info=True)
            await NotificationService.notify_admins_api_error(
                correlation_id,
                "/api/shipping/address",
                user_id,
                payload.order_id,
                e,
                traceback.format_exc()
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=Localizator.get_text(BotEntity.USER, "unauthorized_error")
            )

        except InvalidOrderStateException as e:
            logger.warning(f"[{correlation_id}] Invalid state: {e.current_state}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=Localizator.get_text(BotEntity.USER, "address_already_set_error")
            )

        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error", exc_info=True)
            await NotificationService.notify_admins_api_error(
                correlation_id,
                "/api/shipping/address",
                user_id,
                payload.order_id,
                e,
                traceback.format_exc()
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=Localizator.get_text(BotEntity.USER, "generic_error")
            )