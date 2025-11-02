# Feature: Dialpad Quantity Input (0-9 Keypad)

**Date:** 2025-11-02
**Priority:** Medium
**Status:** Planning
**Estimated Effort:** 3-4 hours
**Type:** UX Enhancement
**Source:** Tester Feedback

---

## Problem

Current quantity selection uses fixed buttons (1-10), which has limitations:
- Cannot select quantities > 10 without multiple interactions
- Takes up a lot of screen space for higher quantities
- Not intuitive for users familiar with numeric input

**Current Implementation:**
```
Item: Digital Item ABC
Available: 50

[1] [2] [3] [4] [5]
[6] [7] [8] [9] [10]
[Back]
```

**User Feedback:**
> "I would like to enter quantity like a dialpad - type the digits (0-9) instead of clicking predefined buttons. For example, to buy 12 items, I tap 1, then 2, and see '12' displayed."

---

## Requested Feature

Implement numeric dialpad interface similar to phone keypads:

```
Item: Digital Item ABC
Available: 50
Quantity: 12

[1] [2] [3]
[4] [5] [6]
[7] [8] [9]
[⌫] [0] [✓]

[Clear] [Back]
```

**Features:**
- Display current quantity being typed
- Buttons 0-9 to build quantity
- Backspace button (⌫) to remove last digit
- Clear button to reset to empty
- Confirm button (✓) to add to cart
- Real-time validation (show available stock)

---

## Solution Design

### Phase 1: FSM State for Quantity Input

**New FSM State:**
```python
# handlers/user/quantity_states.py
class QuantityInputStates(StatesGroup):
    building_quantity = State()  # User is typing quantity on dialpad
```

**State Data:**
```python
{
    "current_quantity": "12",        # String being built
    "item_id": 123,                  # Item being purchased
    "available_stock": 50,           # Max allowed
    "subcategory_id": 5              # For back navigation
}
```

---

### Phase 2: Dialpad Keyboard Builder

**New Utility Function:**
```python
# utils/keyboard_utils.py

def create_quantity_dialpad(
    current_quantity: str,
    item_id: int,
    available_stock: int
) -> InlineKeyboardBuilder:
    """
    Create numeric dialpad for quantity input.

    Layout:
    [1] [2] [3]
    [4] [5] [6]
    [7] [8] [9]
    [⌫] [0] [✓]
    [Clear] [Back]
    """
    kb = InlineKeyboardBuilder()

    # Row 1: 1-3
    for digit in [1, 2, 3]:
        kb.button(
            text=str(digit),
            callback_data=QuantityDialpadCallback.create(
                action="digit",
                value=digit,
                item_id=item_id
            ).pack()
        )
    kb.adjust(3)

    # Row 2: 4-6
    for digit in [4, 5, 6]:
        kb.button(text=str(digit), callback_data=...)
    kb.adjust(3)

    # Row 3: 7-9
    for digit in [7, 8, 9]:
        kb.button(text=str(digit), callback_data=...)
    kb.adjust(3)

    # Row 4: Backspace, 0, Confirm
    kb.button(text="⌫ Backspace", callback_data=...)  # action="backspace"
    kb.button(text="0", callback_data=...)            # action="digit", value=0
    kb.button(text="✓ Confirm", callback_data=...)    # action="confirm"
    kb.adjust(3)

    # Row 5: Clear, Back
    kb.button(text="🗑 Clear", callback_data=...)      # action="clear"
    kb.button(text="« Back", callback_data=...)       # action="back"
    kb.adjust(2)

    return kb
```

---

### Phase 3: Callback Factory

**New Callback:**
```python
# callbacks.py

class QuantityDialpadCallback(CallbackData, prefix="qty_dial"):
    action: str       # "digit", "backspace", "clear", "confirm", "back"
    value: int = 0    # For digit action: 0-9
    item_id: int = 0  # Item being purchased
```

---

### Phase 4: Handler Logic

**Update handlers/user/all_categories.py:**

```python
# Level 1: Show item details (existing)
async def show_item_details(**kwargs):
    # ... existing code ...

    # Replace quantity buttons with dialpad
    kb_builder.button(
        text=Localizator.get_text(BotEntity.USER, "select_quantity"),
        callback_data=AllCategoriesCallback.create(
            level=10,  # New level: Open dialpad
            subcategory_id=subcategory_id,
            item_id=item_id
        ).pack()
    )

# NEW: Level 10: Open Quantity Dialpad
async def open_quantity_dialpad(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")
    unpacked_cb = AllCategoriesCallback.unpack(callback.data)

    item = await ItemRepository.get_by_id(unpacked_cb.item_id, session)

    # Save to FSM
    await state.update_data(
        current_quantity="",
        item_id=item.id,
        available_stock=get_available_stock(item),
        subcategory_id=unpacked_cb.subcategory_id
    )
    await state.set_state(QuantityInputStates.building_quantity)

    # Show dialpad
    msg = Localizator.get_text(BotEntity.USER, "quantity_dialpad_prompt").format(
        item_name=item.description,
        available=get_available_stock(item),
        current_quantity=""
    )

    kb = create_quantity_dialpad("", item.id, get_available_stock(item))
    await callback.message.edit_text(msg, reply_markup=kb.as_markup())


# NEW: Dialpad Action Handler
@all_categories_router.callback_query(
    QuantityDialpadCallback.filter(),
    StateFilter(QuantityInputStates.building_quantity)
)
async def handle_dialpad_action(
    callback: CallbackQuery,
    callback_data: QuantityDialpadCallback,
    state: FSMContext,
    session: AsyncSession | Session
):
    state_data = await state.get_data()
    current_qty = state_data.get("current_quantity", "")

    match callback_data.action:
        case "digit":
            # Append digit
            new_qty = current_qty + str(callback_data.value)

            # Validate
            if int(new_qty) > state_data["available_stock"]:
                await callback.answer(
                    Localizator.get_text(BotEntity.USER, "quantity_exceeds_stock"),
                    show_alert=True
                )
                return

            await state.update_data(current_quantity=new_qty)

        case "backspace":
            # Remove last digit
            new_qty = current_qty[:-1] if current_qty else ""
            await state.update_data(current_quantity=new_qty)

        case "clear":
            # Reset to empty
            await state.update_data(current_quantity="")
            new_qty = ""

        case "confirm":
            # Add to cart
            if not current_qty or int(current_qty) == 0:
                await callback.answer(
                    Localizator.get_text(BotEntity.USER, "quantity_cannot_be_zero"),
                    show_alert=True
                )
                return

            quantity = int(current_qty)
            await CartService.add_to_cart(
                callback_data.item_id,
                quantity,
                callback.from_user.id,
                session
            )

            await state.clear()
            # Show success message and return to item list
            return

        case "back":
            await state.clear()
            # Navigate back to item details
            return

    # Refresh dialpad with new quantity
    item = await ItemRepository.get_by_id(callback_data.item_id, session)
    msg = Localizator.get_text(BotEntity.USER, "quantity_dialpad_prompt").format(
        item_name=item.description,
        available=state_data["available_stock"],
        current_quantity=state_data["current_quantity"]
    )

    kb = create_quantity_dialpad(
        state_data["current_quantity"],
        callback_data.item_id,
        state_data["available_stock"]
    )

    await callback.message.edit_text(msg, reply_markup=kb.as_markup())
```

---

### Phase 5: Localization

**l10n/en.json:**
```json
{
    "select_quantity": "📝 Enter Quantity",
    "quantity_dialpad_prompt": "📦 <b>{item_name}</b>\n\n<b>Available:</b> {available}\n<b>Quantity:</b> {current_quantity}\n\nEnter quantity using the dialpad below:",
    "quantity_exceeds_stock": "⚠️ Quantity cannot exceed available stock!",
    "quantity_cannot_be_zero": "⚠️ Please enter a quantity greater than 0"
}
```

**l10n/de.json:**
```json
{
    "select_quantity": "📝 Menge eingeben",
    "quantity_dialpad_prompt": "📦 <b>{item_name}</b>\n\n<b>Verfügbar:</b> {available}\n<b>Menge:</b> {current_quantity}\n\nGeben Sie die Menge über das Tastenfeld ein:",
    "quantity_exceeds_stock": "⚠️ Menge kann nicht höher als verfügbarer Bestand sein!",
    "quantity_cannot_be_zero": "⚠️ Bitte geben Sie eine Menge größer als 0 ein"
}
```

---

## Implementation Tasks

### Step 1: Foundation (1 hour)
- [ ] Create `QuantityInputStates` in handlers/user/quantity_states.py
- [ ] Create `QuantityDialpadCallback` in callbacks.py
- [ ] Add localization strings (DE/EN)

### Step 2: Keyboard Builder (30 min)
- [ ] Create `create_quantity_dialpad()` in utils/keyboard_utils.py
- [ ] Test button layout and styling

### Step 3: Handler Integration (1.5 hours)
- [ ] Add Level 10 to all_categories.py (open_quantity_dialpad)
- [ ] Implement dialpad action handler
- [ ] Add validation logic (max stock, zero quantity)
- [ ] Update existing Level 1 to link to dialpad

### Step 4: Testing (1 hour)
- [ ] Manual test: Enter single digit (5)
- [ ] Manual test: Enter double digit (12)
- [ ] Manual test: Backspace functionality
- [ ] Manual test: Clear functionality
- [ ] Manual test: Exceed stock validation
- [ ] Manual test: Zero quantity validation
- [ ] Manual test: Back navigation
- [ ] Manual test: Confirm and add to cart

---

## Edge Cases

1. **Empty input + Confirm:** Show error "quantity cannot be zero"
2. **Quantity > Stock:** Show alert, don't update quantity
3. **Leading zeros:** "05" → Display as "5" (strip leading zeros on confirm)
4. **Very large numbers:** Limit input to 4 digits max (9999)
5. **State cleanup:** Clear FSM state on back/confirm

---

## Benefits

**User Experience:**
- More intuitive for entering larger quantities
- Familiar interface (phone dialpad)
- Less screen clutter than 10+ buttons
- Real-time feedback on quantity being entered

**Technical:**
- Scalable solution (works for any quantity)
- Reusable dialpad component
- Clean FSM state management

---

## Alternative Considered

**Text Input:**
User types quantity directly in chat (like shipping address).

**Pros:**
- Even simpler implementation
- No FSM state needed

**Cons:**
- Breaks inline flow (requires switching between message types)
- Less intuitive for Telegram users
- Harder to validate in real-time

**Decision:** Dialpad chosen for better UX continuity

---

## Related Issues

- Consider applying same pattern to:
  - Wallet top-up amount input
  - Custom price input (admin)
  - Shipping cost input (admin)

---

**Status:** Ready for Implementation
**Next Step:** Create QuantityInputStates and QuantityDialpadCallback
