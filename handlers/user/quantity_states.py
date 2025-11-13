"""
FSM States for quantity input using dialpad.
"""
from aiogram.fsm.state import State, StatesGroup


class QuantityInputStates(StatesGroup):
    """States for building quantity using numeric dialpad."""
    building_quantity = State()  # User is typing quantity on dialpad