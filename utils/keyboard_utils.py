"""
Utility functions for building Telegram keyboards.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks import QuantityDialpadCallback
from enums.bot_entity import BotEntity
from utils.localizator import Localizator


def create_quantity_dialpad(
    item_id: int,
    category_id: int,
    subcategory_id: int
) -> InlineKeyboardBuilder:
    """
    Create numeric dialpad for quantity input (phone-style layout).

    Layout:
    [1] [2] [3]
    [4] [5] [6]
    [7] [8] [9]
    [⌫] [0] [✓]
    [Clear] [Back]

    Args:
        item_id: ID of the item being purchased
        category_id: Category ID for navigation context
        subcategory_id: Subcategory ID for navigation context

    Returns:
        InlineKeyboardBuilder with dialpad layout
    """
    kb = InlineKeyboardBuilder()

    # Add all buttons first (don't call adjust() yet!)
    # Row 1: 1-3
    for digit in [1, 2, 3]:
        kb.button(
            text=str(digit),
            callback_data=QuantityDialpadCallback.create(
                action="digit",
                value=digit,
                item_id=item_id,
                category_id=category_id,
                subcategory_id=subcategory_id
            ).pack()
        )

    # Row 2: 4-6
    for digit in [4, 5, 6]:
        kb.button(
            text=str(digit),
            callback_data=QuantityDialpadCallback.create(
                action="digit",
                value=digit,
                item_id=item_id,
                category_id=category_id,
                subcategory_id=subcategory_id
            ).pack()
        )

    # Row 3: 7-9
    for digit in [7, 8, 9]:
        kb.button(
            text=str(digit),
            callback_data=QuantityDialpadCallback.create(
                action="digit",
                value=digit,
                item_id=item_id,
                category_id=category_id,
                subcategory_id=subcategory_id
            ).pack()
        )

    # Row 4: Backspace, 0, Confirm
    kb.button(
        text="⌫",
        callback_data=QuantityDialpadCallback.create(
            action="backspace",
            item_id=item_id,
            category_id=category_id,
            subcategory_id=subcategory_id
        ).pack()
    )
    kb.button(
        text="0",
        callback_data=QuantityDialpadCallback.create(
            action="digit",
            value=0,
            item_id=item_id,
            category_id=category_id,
            subcategory_id=subcategory_id
        ).pack()
    )
    kb.button(
        text="✓",
        callback_data=QuantityDialpadCallback.create(
            action="confirm",
            item_id=item_id,
            category_id=category_id,
            subcategory_id=subcategory_id
        ).pack()
    )

    # Row 5: Clear, Back
    kb.button(
        text=Localizator.get_text(BotEntity.COMMON, "clear_button"),
        callback_data=QuantityDialpadCallback.create(
            action="clear",
            item_id=item_id,
            category_id=category_id,
            subcategory_id=subcategory_id
        ).pack()
    )
    kb.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=QuantityDialpadCallback.create(
            action="back",
            item_id=item_id,
            category_id=category_id,
            subcategory_id=subcategory_id
        ).pack()
    )

    # Now apply layout ONCE at the end
    # 3 buttons per row for rows 1-4, then 2 buttons for row 5
    kb.adjust(3, 3, 3, 3, 2)

    return kb