from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import json
import logging

import config
from callbacks import OrderCallback
from enums.bot_entity import BotEntity
from handlers.user.shipping_states import ShippingAddressStates
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator
from utils.webapp_url import get_webapp_url
from exceptions.shipping import BotDomainNotConfiguredException

shipping_router = Router()


@shipping_router.message(ShippingAddressStates.waiting_for_address, IsUserExistFilter())
async def process_shipping_address_input(message: Message, state: FSMContext, session: AsyncSession | Session):
    """
    Process user's shipping address input (free-text).
    Shows confirmation screen with address preview.
    """
    address_text = message.text.strip()

    if not address_text or len(address_text) < 10:
        # Address too short - ask again
        await message.answer(
            Localizator.get_text(BotEntity.USER, "shipping_address_invalid")
        )
        return

    # Store address in FSM context
    await state.update_data(shipping_address=address_text)

    # Show confirmation screen
    from utils.html_escape import safe_html
    message_text = Localizator.get_text(BotEntity.USER, "shipping_address_confirm").format(
        address=safe_html(address_text),
        retention_days=config.DATA_RETENTION_DAYS
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=OrderCallback.create(level=1).pack()  # Level 1 = confirm address
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.USER, "change_address"),
        callback_data=OrderCallback.create(level=2).pack()  # Level 2 = re-enter address
    )

    await message.answer(message_text, reply_markup=kb_builder.as_markup())
    await state.set_state(ShippingAddressStates.confirm_address)


@shipping_router.message(ShippingAddressStates.waiting_for_address, F.web_app_data, IsUserExistFilter())
async def process_pgp_encrypted_address(message: Message, state: FSMContext, session: AsyncSession | Session):
    """
    Process PGP-encrypted shipping address from Telegram Mini App.

    The Mini App sends JSON data via tg.sendData():
    {
         "order_id": 0,  # Ignored - order doesn't exist yet
        "encrypted_address": "-----BEGIN PGP MESSAGE-----...",
        "encryption_mode": "pgp"
    }

    This handler stores the encrypted address in FSM state (same as plaintext handler).
    The address will be saved to the order during order creation.
    """
    logging.info(f"[Shipping] PGP handler triggered - User: {message.from_user.id}")

    try:
        # Parse WebApp data (DO NOT log content - may contain PII)
        logging.info(f"[Shipping] Parsing web_app_data (length: {len(message.web_app_data.data)})")
        web_app_data = json.loads(message.web_app_data.data)
        encrypted_address = web_app_data.get("encrypted_address")
        encryption_mode = web_app_data.get("encryption_mode")

        if not encrypted_address or encryption_mode != "pgp":
            await message.answer(
                "❌ Invalid data received from Mini App. Please try again."
            )
            return

        # Store encrypted address in FSM context (with encryption mode flag)
        await state.update_data(
            shipping_address=encrypted_address,
            encryption_mode="pgp"
        )

        # Show confirmation screen (same as plaintext handler)
        message_text = Localizator.get_text(BotEntity.USER, "shipping_address_confirm_encrypted").format(
            retention_days=config.DATA_RETENTION_DAYS
        )

        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "confirm"),
            callback_data=OrderCallback.create(level=1).pack()  # Level 1 = confirm address
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "change_address"),
            callback_data=OrderCallback.create(level=2).pack()  # Level 2 = re-enter address
        )

        await message.answer(message_text, reply_markup=kb_builder.as_markup())
        await state.set_state(ShippingAddressStates.confirm_address)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse WebApp data: {e}")
        await message.answer(
            "❌ Invalid data format. Please try again."
        )
    except Exception as e:
        logging.error(f"Error processing PGP address: {e}")
        await message.answer(
            Localizator.get_text(BotEntity.ADMIN, "error_unexpected")
        )


def get_pgp_input_button(order_id: int, lang: str = "de") -> InlineKeyboardBuilder | None:
    """
    Create a button for PGP-encrypted address input via Telegram Mini App.

    Returns None if PGP not configured or domain cannot be determined.

    Args:
        order_id: Order ID to associate with encrypted address
        lang: Language code for Mini App

    Returns:
        InlineKeyboardBuilder with WebApp button, or None if PGP not available
    """
    try:
        # Check if PGP encryption is available (only check public key)
        # BOT_DOMAIN is optional - get_webapp_url() can determine it dynamically
        if not config.PGP_PUBLIC_KEY_BASE64:
            logging.info("[Shipping] PGP not available - missing PGP_PUBLIC_KEY_BASE64")
            return None

        # Generate WebApp URL (handles dynamic domain lookup)
        webapp_url = get_webapp_url(
            endpoint="/webapp/pgp-address-input",
            lang=lang,
            order_id=order_id
        )
        logging.info(f"[Shipping] PGP encryption available - WebApp URL: {webapp_url[:50]}...")

        # Create button with WebApp
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "pgp_webapp_main_button"),
            web_app=WebAppInfo(url=webapp_url)
        )

        return kb_builder

    except BotDomainNotConfiguredException as e:
        logging.warning(f"[Shipping] BOT_DOMAIN not configured and dynamic lookup failed - PGP input not available: {e}")
        return None
    except Exception as e:
        logging.error(f"Error creating PGP input button: {e}")
        return None


# Note: Shipping address confirmation is handled in handlers/user/order.py Level 1
# which calls OrderService.confirm_shipping_address()
