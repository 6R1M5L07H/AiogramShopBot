from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import AllCategoriesCallback
from enums.bot_entity import BotEntity
from handlers.common.common import add_pagination_buttons
from models.item import ItemDTO
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from utils.localizator import Localizator


class SubcategoryService:

    @staticmethod
    async def get_buttons(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = AllCategoriesCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        subcategories = await SubcategoryRepository.get_paginated_by_category_id(unpacked_cb.category_id,
                                                                                 unpacked_cb.page, session)
        for subcategory in subcategories:
            item = await ItemRepository.get_single(unpacked_cb.category_id, subcategory.id, session)
            available_qty = await ItemRepository.get_available_qty(ItemDTO(category_id=unpacked_cb.category_id,
                                                                           subcategory_id=subcategory.id), session)

            # Skip subcategories with zero stock (sold out or all reserved) or no items
            if available_qty == 0 or item is None:
                continue

            kb_builder.button(text=Localizator.get_text(BotEntity.USER, "subcategory_button").format(
                subcategory_name=subcategory.name,
                subcategory_price=item.price,
                available_quantity=available_qty,
                currency_sym=Localizator.get_currency_symbol()),
                callback_data=AllCategoriesCallback.create(
                    unpacked_cb.level + 1,
                    unpacked_cb.category_id,
                    subcategory.id
                )
            )
        kb_builder.adjust(1)
        kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                  SubcategoryRepository.max_page(unpacked_cb.category_id, session),
                                                  unpacked_cb.get_back_button())
        return Localizator.get_text(BotEntity.USER, "subcategories"), kb_builder

    @staticmethod
    async def get_select_quantity_buttons(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = AllCategoriesCallback.unpack(callback.data)
        item = await ItemRepository.get_single(unpacked_cb.category_id, unpacked_cb.subcategory_id, session)
        subcategory = await SubcategoryRepository.get_by_id(unpacked_cb.subcategory_id, session)
        category = await CategoryRepository.get_by_id(unpacked_cb.category_id, session)

        # If no item exists (all sold/reserved), show error
        from exceptions.item import ItemNotFoundException

        if item is None:
            raise ItemNotFoundException(
                category_id=unpacked_cb.category_id,
                subcategory_id=unpacked_cb.subcategory_id
            )

        available_qty = await ItemRepository.get_available_qty(item, session)

        # Check for tiered pricing
        from services.pricing import PricingService
        tier_display = await PricingService.format_available_tiers(unpacked_cb.subcategory_id, session)

        # Build message with shipping info for physical items
        if item.is_physical:
            message_text = Localizator.get_text(BotEntity.USER, "select_quantity_with_shipping").format(
                category_name=category.name,
                subcategory_name=subcategory.name,
                price=item.price,
                shipping_cost=item.shipping_cost,
                description=item.description,
                quantity=available_qty,
                currency_sym=Localizator.get_currency_symbol()
            )
        else:
            message_text = Localizator.get_text(BotEntity.USER, "select_quantity").format(
                category_name=category.name,
                subcategory_name=subcategory.name,
                price=item.price,
                description=item.description,
                quantity=available_qty,
                currency_sym=Localizator.get_currency_symbol()
            )

        # Add tier display if available
        if tier_display:
            message_text += "\n\n" + tier_display
        kb_builder = InlineKeyboardBuilder()
        for i in range(1, 11):
            kb_builder.button(text=str(i), callback_data=AllCategoriesCallback.create(
                unpacked_cb.level + 1,
                item.category_id,
                item.subcategory_id,
                quantity=i
            ))
        kb_builder.adjust(3)
        kb_builder.row(unpacked_cb.get_back_button())
        return message_text, kb_builder

    @staticmethod
    async def _calculate_cart_tier_pricing(
        subcategory_id: int,
        new_quantity: int,
        telegram_id: int,
        session: AsyncSession | Session
    ) -> tuple[int, int, object]:
        """
        Calculate tier pricing including existing cart items.

        Args:
            subcategory_id: ID of the subcategory
            new_quantity: New quantity to add
            telegram_id: User's Telegram ID
            session: Database session

        Returns:
            Tuple of (existing_quantity, total_quantity, pricing_result)
        """
        from repositories.cart import CartRepository
        from repositories.user import UserRepository
        from services.pricing import PricingService

        # Get user's cart
        user = await UserRepository.get_by_tgid(telegram_id, session)
        cart = await CartRepository.get_or_create(user.id, session)

        # Check for existing items in cart
        existing_items = await CartRepository.get_items_by_subcategory(
            cart.id,
            subcategory_id,
            session
        )

        # Calculate quantities
        existing_quantity = sum(ci.quantity for ci in existing_items) if existing_items else 0
        total_quantity = existing_quantity + new_quantity

        # Calculate tier pricing for TOTAL quantity
        pricing_result = await PricingService.calculate_optimal_price(
            subcategory_id=subcategory_id,
            quantity=total_quantity,
            session=session
        )

        return existing_quantity, total_quantity, pricing_result

    @staticmethod
    async def get_add_to_cart_buttons(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        """
        Show tier preview with pricing breakdown before adding to cart.
        """
        from exceptions.item import ItemNotFoundException
        from services.pricing import PricingService

        unpacked_cb = AllCategoriesCallback.unpack(callback.data)
        item = await ItemRepository.get_single(unpacked_cb.category_id, unpacked_cb.subcategory_id, session)
        subcategory = await SubcategoryRepository.get_by_id(unpacked_cb.subcategory_id, session)

        if item is None:
            raise ItemNotFoundException(
                category_id=unpacked_cb.category_id,
                subcategory_id=unpacked_cb.subcategory_id
            )

        # Calculate tier pricing with cart context
        existing_qty, total_qty, pricing_result = await SubcategoryService._calculate_cart_tier_pricing(
            subcategory_id=unpacked_cb.subcategory_id,
            new_quantity=unpacked_cb.quantity,
            telegram_id=callback.from_user.id,
            session=session
        )

        # Build message
        message_parts = [
            f"<b>{subcategory.name}</b>",
            f"{item.description}\n"
        ]

        # Show cart context
        if existing_qty > 0:
            message_parts.append(
                f"ℹ️ {Localizator.get_text(BotEntity.USER, 'tier_preview_already_in_cart').format(existing_quantity=existing_qty)}"
            )
            message_parts.append(
                f"📊 {Localizator.get_text(BotEntity.USER, 'tier_preview_new_total').format(total_quantity=total_qty)}\n"
            )
        else:
            message_parts.append(
                f"📦 {Localizator.get_text(BotEntity.USER, 'tier_preview_quantity').format(quantity=total_qty)}\n"
            )

        # Add tier breakdown
        message_parts.append(PricingService.format_tier_breakdown(pricing_result))

        message_text = "\n".join(message_parts)

        # Build buttons
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=unpacked_cb.get_back_button().callback_data
        )
        kb_builder.button(
            text="✅ " + Localizator.get_text(BotEntity.USER, "tier_preview_add_to_cart"),
            callback_data=AllCategoriesCallback.create(
                unpacked_cb.level + 1,
                unpacked_cb.category_id,
                unpacked_cb.subcategory_id,
                quantity=unpacked_cb.quantity,
                confirmation=True
            )
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "cancel"),
            callback_data=AllCategoriesCallback.create(1, unpacked_cb.category_id)
        )
        kb_builder.adjust(3)

        return message_text, kb_builder
