from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import OrderCallback
from enums.bot_entity import BotEntity
from handlers.user.shipping_states import ShippingAddressStates
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

shipping_router = Router()


@shipping_router.message(ShippingAddressStates.waiting_for_address, IsUserExistFilter())
async def process_shipping_address_input(message: Message, state: FSMContext, session: AsyncSession | Session):
    """
    Process user's shipping address input (free-text, manual input).
    Bot will AES-encrypt this plaintext address.
    Shows confirmation screen with address preview.
    """
    address_text = message.text.strip()

    if not address_text or len(address_text) < 10:
        # Address too short - ask again
        await message.answer(
            Localizator.get_text(BotEntity.USER, "shipping_address_invalid")
        )
        return

    # Store address in FSM context with AES-GCM mode
    await state.update_data(
        shipping_address=address_text,
        encryption_mode="aes-gcm"
    )

    # Show confirmation screen
    message_text = Localizator.get_text(BotEntity.USER, "shipping_address_confirm").format(
        address=address_text,
        retention_days=config.DATA_RETENTION_DAYS
    )

    # Get order_id from FSM context
    fsm_data = await state.get_data()
    order_id = fsm_data.get("order_id")

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=OrderCallback.create(level=1, order_id=order_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.USER, "change_address"),
        callback_data=OrderCallback.create(level=2, order_id=order_id).pack()
    )

    await message.answer(message_text, reply_markup=kb_builder.as_markup())
    await state.set_state(ShippingAddressStates.confirm_address)


# Note: Shipping address confirmation is handled in handlers/user/order.py Level 1
# which calls OrderService.confirm_shipping_address()


@shipping_router.message(F.web_app_data, IsUserExistFilter())
async def process_pgp_encrypted_address(message: Message, state: FSMContext, session: AsyncSession | Session):
    """
    Process PGP-encrypted shipping address from Telegram Mini App.

    Mini App sends JSON: {"encrypted_address": "...", "encryption_mode": "pgp"}
    """
    import json
    import logging

    try:
        # Parse WebApp data
        webapp_data = json.loads(message.web_app_data.data)
        encrypted_address = webapp_data.get("encrypted_address")
        encryption_mode = webapp_data.get("encryption_mode")

        if not encrypted_address or encryption_mode != "pgp":
            raise ValueError("Invalid WebApp data format")

        logging.info(f"📦 Received PGP-encrypted address from user {message.from_user.id}")

        # Store encrypted address in FSM context
        await state.update_data(
            shipping_address=encrypted_address,
            encryption_mode="pgp"
        )

        # Show confirmation screen
        message_text = Localizator.get_text(BotEntity.USER, "shipping_pgp_confirm").format(
            retention_days=config.DATA_RETENTION_DAYS
        )

        # Get order_id from FSM context (set during order creation)
        fsm_data = await state.get_data()
        order_id = fsm_data.get("order_id")

        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "confirm"),
            callback_data=OrderCallback.create(level=1, order_id=order_id).pack()
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "change_address"),
            callback_data=OrderCallback.create(level=2, order_id=order_id).pack()
        )

        await message.answer(message_text, reply_markup=kb_builder.as_markup())
        await state.set_state(ShippingAddressStates.confirm_address)

    except Exception as e:
        logging.error(f"Failed to process WebApp data: {e}")
        await message.answer(
            Localizator.get_text(BotEntity.USER, "shipping_pgp_error")
        )
