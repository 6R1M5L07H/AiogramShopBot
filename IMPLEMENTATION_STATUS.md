# Shipping Management System - Implementation Status

**Branch:** `feature/shipping-management-system`
**Status:** Phase 1 Complete (40% done) - Database & Validation
**Last Update:** 2025-10-23 02:00

---

## ✅ Phase 1: Database Models & Validation (COMPLETE)

### Database Models

**Item Model** (`models/item.py`)
```python
# New fields added:
is_physical = Column(Boolean, nullable=False, default=True)
shipping_cost = Column(Float, nullable=False, default=0.0)
packstation_allowed = Column(Boolean, nullable=False, default=True)
```

**ItemDTO** - Updated with same fields

**Order Model** (`models/order.py`)
```python
# New fields:
shipping_cost = Column(Float, nullable=False, default=0.0)
shipping_address = relationship('ShippingAddress', ...)  # One-to-one
```

**OrderDTO** - Updated with shipping_cost

**ShippingAddress Model** (`models/shipping_address.py`) - NEW FILE
```python
class ShippingAddress(Base):
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True)
    address_encrypted = Column(LargeBinary, nullable=False)  # AES-256-GCM encrypted
    created_at = Column(DateTime, default=func.now())
```

**OrderStatus Enum** (`enums/order_status.py`)
```python
# Added new statuses:
AWAITING_SHIPMENT = "AWAITING_SHIPMENT"  # After payment, before shipping
SHIPPED = "SHIPPED"                       # Marked as shipped by admin
```

### Encryption

**AddressEncryption Utility** (`utils/encryption.py`) - NEW FILE
- AES-256-GCM authenticated encryption
- Random 96-bit nonce per encryption
- Key from env: `SHIPPING_ADDRESS_ENCRYPTION_KEY` (32 bytes / 64 hex chars)
- Methods: `encrypt(plaintext: str) -> bytes`, `decrypt(encrypted: bytes) -> str`

**ShippingAddressRepository** (`repositories/shipping_address.py`) - NEW FILE
- `create(order_id, plaintext_address, session)` - Encrypts and stores
- `get_by_order_id(order_id, session)` - Returns ShippingAddress object
- `get_decrypted_address(order_id, session)` - Returns decrypted string
- `delete_by_order_id(order_id, session)` - Cleanup

### JSON Import Validation

**ItemService.parse_items_json()** (`services/item.py`)
```python
# NEW VALIDATION LOGIC:
is_physical = item.get('is_physical', True)

if not is_physical:
    # Digital: Auto-set shipping fields to 0.0
    item['shipping_cost'] = 0.0
    item['packstation_allowed'] = True
else:
    # Physical: REQUIRE both fields or error
    if 'shipping_cost' not in item:
        raise ValueError("Physical item missing 'shipping_cost'")
    if 'packstation_allowed' not in item:
        raise ValueError("Physical item missing 'packstation_allowed'")
```

**Example Valid JSONs:**

Physical Item:
```json
{
  "category": "Supplements",
  "subcategory": "Vitamin D",
  "price": 19.99,
  "is_physical": true,
  "shipping_cost": 1.50,
  "packstation_allowed": false,
  "description": "High-dose Vitamin D",
  "private_data": "VIT-D-001"
}
```

Digital Item:
```json
{
  "category": "eBooks",
  "subcategory": "Programming Guide",
  "price": 9.99,
  "is_physical": false,
  "description": "Learn Python",
  "private_data": "EBOOK-PY-001"
}
```

---

## 🔄 Phase 2-6: TODO (60% remaining)

### Phase 2: Order Service Updates (NOT STARTED)

**Required Changes in `services/order.py`:**

```python
async def create_order_from_cart(...):
    # Calculate max shipping cost from cart items
    max_shipping = 0.0
    has_physical_items = False

    for cart_item in cart_items:
        item = await ItemRepository.get_single(...)
        if item.is_physical:
            has_physical_items = True
            if item.shipping_cost > max_shipping:
                max_shipping = item.shipping_cost

    # Calculate total
    items_total = ...  # existing logic
    order_total = items_total + max_shipping

    # Create order
    order_dto = OrderDTO(
        ...
        total_price=order_total,
        shipping_cost=max_shipping,
        status=OrderStatus.PENDING_PAYMENT
    )

    # After payment completion:
    if has_physical_items:
        # Status → AWAITING_SHIPMENT (not delivered yet!)
        await OrderRepository.update_status(order_id, OrderStatus.AWAITING_SHIPMENT, session)
    else:
        # Digital items → Deliver immediately
        await deliver_items(...)
```

**Shipping Cost Logic:**
- `max(item.shipping_cost for item in cart where item.is_physical)`
- Applied once per order (not per item)
- Stored in `Order.shipping_cost`

### Phase 3: Address Collection FSM (NOT STARTED)

**FSM States Needed** (`handlers/user/states.py` or similar):

```python
class CheckoutStates(StatesGroup):
    # ... existing states ...
    waiting_for_shipping_address = State()
    confirm_shipping_address = State()
```

**Flow:**
```
Cart Review → [Check if has physical items]
  ↓ Yes
Address Input Screen
  ↓
User enters address (single message, free-form text)
  ↓
Confirmation Screen (show address, "Correct?" [Yes/No/Edit])
  ↓ Yes
Crypto Selection → Invoice → Payment
```

**Packstation Warning Logic:**
```python
# Check if any item disallows packstation
packstation_warning = False
for cart_item in cart_items:
    item = await ItemRepository.get_single(...)
    if item.is_physical and not item.packstation_allowed:
        packstation_warning = True
        break

if packstation_warning:
    message += "\n\n⚠️ Hinweis: Deine Bestellung enthält Artikel, die NICHT an Packstationen geliefert werden können. Bitte gib eine Hausadresse an."
```

**Handler Structure** (needs creation):
```python
# handlers/user/checkout_address.py (NEW FILE)

@router.message(StateFilter(CheckoutStates.waiting_for_shipping_address))
async def receive_shipping_address(message: Message, state: FSMContext):
    address_text = message.text.strip()

    # Basic validation (min length)
    if len(address_text) < 10:
        await message.answer("Adresse zu kurz. Bitte vollständige Adresse eingeben.")
        return

    # Store in FSM for confirmation
    await state.update_data(shipping_address=address_text)
    await state.set_state(CheckoutStates.confirm_shipping_address)

    # Show confirmation
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Korrekt", callback_data=...)
    kb.button(text="✗ Neu eingeben", callback_data=...)

    await message.answer(
        f"✅ Bestätige deine Versandadresse:\n\n{address_text}\n\nIst diese Adresse korrekt?",
        reply_markup=kb.as_markup()
    )

@router.callback_query(StateFilter(CheckoutStates.confirm_shipping_address))
async def confirm_address(callback: CallbackQuery, state: FSMContext):
    if callback.data == "address_confirmed":
        data = await state.get_data()
        address = data['shipping_address']

        # Save encrypted address with order (after order created)
        # Continue to crypto selection
        await show_crypto_selection(...)
    else:
        # Re-prompt for address
        await state.set_state(CheckoutStates.waiting_for_shipping_address)
        await callback.message.edit_text("Bitte gib deine Versandadresse erneut ein:")
```

### Phase 4: Cart Display Updates (NOT STARTED)

**Required Changes in `services/cart.py`:**

```python
# In cart display method:
async def show_cart(...):
    # ... existing cart items display ...

    # Calculate shipping
    max_shipping = 0.0
    for cart_item in cart_items:
        item = await ItemRepository.get_single(...)
        if item.is_physical and item.shipping_cost > max_shipping:
            max_shipping = item.shipping_cost

    items_total = sum(...)  # existing
    order_total = items_total + max_shipping

    message += f"\n\n"
    message += f"Artikel: {currency_sym}{items_total:.2f}\n"

    if max_shipping > 0:
        message += f"Versand: {currency_sym}{max_shipping:.2f}\n"

    message += f"━━━━━━━━━━━━━━━━\n"
    message += f"<b>Gesamt: {currency_sym}{order_total:.2f}</b>"
```

### Phase 5: Admin Shipping Interface (NOT STARTED)

**New Admin Handler** (`handlers/admin/shipping.py` - NEW FILE):

```python
from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.order import OrderRepository
from repositories.shipping_address import ShippingAddressRepository
from enums.order_status import OrderStatus

shipping_router = Router()

@shipping_router.callback_query(...)
async def list_awaiting_shipment(callback: CallbackQuery, session: AsyncSession):
    """Show orders awaiting shipment"""
    orders = await OrderRepository.get_by_status(
        OrderStatus.AWAITING_SHIPMENT,
        session
    )

    message = f"📦 <b>Bestellungen warten auf Versand</b>\n\nAnzahl: {len(orders)}\n\n"

    kb = InlineKeyboardBuilder()

    for order in orders:
        # Get invoice number
        invoice = await InvoiceRepository.get_by_order_id(order.id, session)
        invoice_num = invoice.invoice_number if invoice else f"#{order.id}"

        # Get decrypted address
        address = await ShippingAddressRepository.get_decrypted_address(order.id, session)

        # Create button for each order
        kb.button(
            text=f"{invoice_num} - €{order.total_price:.2f}",
            callback_data=ShippingCallback.create(order.id)
        )

        message += f"📋 {invoice_num}\n"
        message += f"📦 {address[:50]}...\n"  # First 50 chars
        message += f"💵 €{order.total_price:.2f}\n\n"

    kb.adjust(1)
    await callback.message.edit_text(message, reply_markup=kb.as_markup())

@shipping_router.callback_query(...)
async def show_order_details(callback: CallbackQuery, session: AsyncSession):
    """Show full order details with ship button"""
    order_id = ...  # from callback data

    order = await OrderRepository.get_by_id(order_id, session)
    address = await ShippingAddressRepository.get_decrypted_address(order_id, session)
    items = await ItemRepository.get_by_order_id(order_id, session)

    message = f"📦 <b>Bestellung Details</b>\n\n"
    message += f"Invoice: {invoice_number}\n"
    message += f"Datum: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    message += f"<b>Versandadresse:</b>\n{address}\n\n"
    message += f"<b>Artikel:</b>\n"

    for item in items:
        subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
        message += f"- {subcategory.name}\n"

    message += f"\n💵 Gesamt: €{order.total_price:.2f}"

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Als versendet markieren", callback_data=ShippingCallback.create_mark_shipped(order_id))
    kb.button(text="↩️ Zurück", callback_data=...)

    await callback.message.edit_text(message, reply_markup=kb.as_markup())

@shipping_router.callback_query(...)
async def mark_as_shipped(callback: CallbackQuery, session: AsyncSession):
    """Mark order as shipped"""
    order_id = ...  # from callback data

    # Update status
    await OrderRepository.update_status(order_id, OrderStatus.SHIPPED, session)
    await session_commit(session)

    # Send user notification
    order = await OrderRepository.get_by_id(order_id, session)
    user = await UserRepository.get_by_id(order.user_id, session)

    await NotificationService.send_order_shipped(user, order, session)

    await callback.answer("✅ Bestellung als versendet markiert!")
    await list_awaiting_shipment(callback, session)  # Back to list
```

**Required Repository Method** (`repositories/order.py`):
```python
@staticmethod
async def get_by_status(status: OrderStatus, session: AsyncSession) -> list[Order]:
    """Get all orders with specific status"""
    stmt = select(Order).where(Order.status == status).order_by(Order.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()
```

### Phase 6: Notifications & Localization (NOT STARTED)

**Notification Service** (`services/notification.py`):

```python
# Add new method:
@staticmethod
async def send_order_shipped(user: User, order: Order, session: AsyncSession):
    """Send notification when order shipped"""
    invoice = await InvoiceRepository.get_by_order_id(order.id, session)
    invoice_number = invoice.invoice_number if invoice else f"#{order.id}"

    message = Localizator.get_text(BotEntity.USER, "order_shipped_notification").format(
        invoice_number=invoice_number
    )

    await NotificationService.send_to_user(message, user.telegram_id)
```

**Localization Keys** (`l10n/de.json` and `l10n/en.json`):

```json
// de.json
{
  "shipping_address_prompt": "📦 <b>Versandadresse</b>\n\nBitte gib deine vollständige Versandadresse ein:\n\nBeispiel:\nMax Mustermann\nMusterstraße 123\nZusatz: Hinterhaus (optional)\n12345 Musterstadt\nDeutschland",

  "shipping_address_too_short": "❌ Adresse zu kurz. Bitte vollständige Adresse eingeben (Name, Straße, PLZ, Stadt, Land).",

  "confirm_shipping_address": "✅ <b>Bestätige deine Versandadresse:</b>\n\n{address}\n\nIst diese Adresse korrekt?",

  "packstation_warning": "⚠️ <b>Wichtig:</b> Deine Bestellung enthält Artikel, die NICHT an Packstationen geliefert werden können. Bitte gib eine Hausadresse an.",

  "shipping_cost_label": "Versand",
  "items_subtotal_label": "Artikel",
  "total_with_shipping_label": "Gesamt",

  "order_awaiting_shipment": "⏳ Deine Bestellung wird für den Versand vorbereitet.",

  "order_shipped_notification": "📦 <b>Deine Bestellung wurde versendet!</b>\n\nBestellnummer: {invoice_number}\n\nDeine Bestellung ist unterwegs. Du solltest sie in den nächsten Tagen erhalten.",

  "admin_awaiting_shipment_list": "📦 <b>Bestellungen warten auf Versand</b>\n\nAnzahl: {count}",
  "admin_mark_as_shipped": "✅ Als versendet markieren",
  "admin_order_marked_shipped": "✅ Bestellung als versendet markiert!",

  "address_input_button": "📝 Adresse eingeben",
  "address_confirm_button": "✅ Korrekt",
  "address_edit_button": "✏️ Neu eingeben"
}

// en.json (same keys in English)
{
  "shipping_address_prompt": "📦 <b>Shipping Address</b>\n\nPlease enter your complete shipping address:\n\nExample:\nJohn Doe\nMain Street 42\nApt 5B\n10115 Berlin\nGermany",

  "shipping_address_too_short": "❌ Address too short. Please enter complete address (Name, Street, Postal Code, City, Country).",

  "confirm_shipping_address": "✅ <b>Confirm your shipping address:</b>\n\n{address}\n\nIs this address correct?",

  "packstation_warning": "⚠️ <b>Important:</b> Your order contains items that cannot be delivered to Packstations. Please provide a home address.",

  "shipping_cost_label": "Shipping",
  "items_subtotal_label": "Items",
  "total_with_shipping_label": "Total",

  "order_awaiting_shipment": "⏳ Your order is being prepared for shipment.",

  "order_shipped_notification": "📦 <b>Your order has been shipped!</b>\n\nOrder number: {invoice_number}\n\nYour order is on its way. You should receive it in the next few days.",

  "admin_awaiting_shipment_list": "📦 <b>Orders Awaiting Shipment</b>\n\nCount: {count}",
  "admin_mark_as_shipped": "✅ Mark as Shipped",
  "admin_order_marked_shipped": "✅ Order marked as shipped!",

  "address_input_button": "📝 Enter Address",
  "address_confirm_button": "✅ Correct",
  "address_edit_button": "✏️ Re-enter"
}
```

---

## 🔧 Required Configuration

**Environment Variables** (add to `.env.template`):

```bash
# ----------------------------------------------------------------------------
# SHIPPING ADDRESS ENCRYPTION
# ----------------------------------------------------------------------------

# AES-256 encryption key for shipping addresses (32 bytes = 64 hex characters)
# Generate with: openssl rand -hex 32
# IMPORTANT: Keep this secret! Do not commit to git!
# Example: 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b
SHIPPING_ADDRESS_ENCRYPTION_KEY=
```

---

## 📋 Migration Required

**Database Changes** (SQLite):
```sql
-- Add shipping fields to items table
ALTER TABLE items ADD COLUMN is_physical BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE items ADD COLUMN shipping_cost FLOAT NOT NULL DEFAULT 0.0;
ALTER TABLE items ADD COLUMN packstation_allowed BOOLEAN NOT NULL DEFAULT TRUE;

-- Add shipping_cost to orders table
ALTER TABLE orders ADD COLUMN shipping_cost FLOAT NOT NULL DEFAULT 0.0;

-- Create shipping_addresses table
CREATE TABLE shipping_addresses (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE,
    address_encrypted BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- Note: OrderStatus enum values automatically handled by SQLAlchemy
-- AWAITING_SHIPMENT and SHIPPED will be available after restart
```

**Migration Script** (manual for now):
```python
# migrations/add_shipping_fields.py (if using alembic)
def upgrade():
    op.add_column('items', sa.Column('is_physical', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('items', sa.Column('shipping_cost', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('items', sa.Column('packstation_allowed', sa.Boolean(), nullable=False, server_default='1'))

    op.add_column('orders', sa.Column('shipping_cost', sa.Float(), nullable=False, server_default='0.0'))

    op.create_table(
        'shipping_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('address_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )
```

---

## ✅ Testing Checklist

### Phase 1 (Completed)
- [x] Item model has new fields
- [x] ItemDTO updated
- [x] Order model has shipping_cost
- [x] OrderDTO updated
- [x] ShippingAddress model created
- [x] OrderStatus enum extended
- [x] AddressEncryption utility created
- [x] ShippingAddressRepository created
- [x] JSON import validation working

### Phase 2-6 (TODO)
- [ ] OrderService calculates max shipping cost
- [ ] Order total includes shipping
- [ ] Physical orders → AWAITING_SHIPMENT status
- [ ] Digital orders skip shipping
- [ ] FSM address collection flow
- [ ] Address confirmation screen
- [ ] Packstation warning display
- [ ] Cart shows shipping breakdown
- [ ] Admin can list awaiting shipment orders
- [ ] Admin can view decrypted addresses
- [ ] Admin can mark as shipped
- [ ] User receives shipped notification
- [ ] Localization keys added (DE/EN)
- [ ] Mixed cart (physical + digital) works correctly

---

## 🚨 Known Issues / Edge Cases

1. **Address Format Flexibility**
   - User can enter any format (good for flexibility)
   - No validation of actual address format
   - Admin responsibility to handle invalid addresses

2. **Packstation Warning**
   - Warning shown if ANY item disallows packstation
   - User could still enter packstation address (we trust user)
   - No enforcement, just warning

3. **Shipping Cost Calculation**
   - Max cost applied once per order (correct)
   - Multiple items with same max cost → still only charged once
   - Transparent in cart display

4. **Order Status Flow**
   - Physical orders: PAID → AWAITING_SHIPMENT → SHIPPED
   - Digital orders: PAID → (deliver immediately, no status change needed)
   - Mixed orders: Treated as physical (if ANY physical item)

5. **Address Encryption**
   - Requires SHIPPING_ADDRESS_ENCRYPTION_KEY in .env
   - If key is lost, all addresses unrecoverable (document this!)
   - Key rotation not implemented (future enhancement)

6. **Data Retention**
   - Shipping addresses deleted with order after DATA_RETENTION_DAYS
   - Consider separate retention period for addresses? (shorter for privacy?)

---

## 🎯 Next Steps (Priority Order)

1. **HIGH PRIORITY:**
   - [ ] Update OrderService.create_order_from_cart() for shipping calculation
   - [ ] Create address collection FSM handlers
   - [ ] Update cart display with shipping breakdown
   - [ ] Generate encryption key and add to .env.template
   - [ ] Database migration script

2. **MEDIUM PRIORITY:**
   - [ ] Create admin shipping management interface
   - [ ] Implement mark as shipped functionality
   - [ ] Add all localization keys (DE/EN)
   - [ ] User shipped notification

3. **LOW PRIORITY:**
   - [ ] Testing with real data
   - [ ] Documentation updates
   - [ ] Error handling improvements

---

## 💾 Files Modified/Created

### Created:
- `models/shipping_address.py` - ShippingAddress model
- `repositories/shipping_address.py` - CRUD with encryption
- `utils/encryption.py` - AES-256-GCM utility
- `IMPLEMENTATION_STATUS.md` - This file

### Modified:
- `models/item.py` - Added shipping fields (is_physical, shipping_cost, packstation_allowed)
- `models/order.py` - Added shipping_cost field and shipping_address relationship
- `enums/order_status.py` - Added AWAITING_SHIPMENT and SHIPPED statuses
- `services/item.py` - Added JSON import validation for shipping fields

### TODO (Not Yet Created):
- `handlers/user/checkout_address.py` - Address collection FSM
- `handlers/admin/shipping.py` - Admin shipping management interface
- `callbacks/shipping.py` - Shipping callback classes (if needed)
- `.env.template` - Add SHIPPING_ADDRESS_ENCRYPTION_KEY

### TODO (Not Yet Modified):
- `services/order.py` - Shipping cost calculation in create_order_from_cart()
- `services/cart.py` - Cart display with shipping breakdown
- `services/notification.py` - Order shipped notification
- `l10n/de.json` - All German localization keys
- `l10n/en.json` - All English localization keys

---

## 📊 Progress Summary

**Overall: 40% Complete**

✅ Phase 1: Database & Validation (100%)
🔄 Phase 2: Order Service Updates (0%)
🔄 Phase 3: Address Collection FSM (0%)
🔄 Phase 4: Cart Display Updates (0%)
🔄 Phase 5: Admin Interface (0%)
🔄 Phase 6: Notifications & L10n (0%)

**Estimated Remaining Time:** 3-4 hours for Phases 2-6

---

## 🔐 Security Considerations

1. **Encryption Key Management**
   - Key stored in .env (not ideal but acceptable for MVP)
   - Future: Consider key vault (AWS KMS, HashiCorp Vault)
   - Key rotation strategy needed for production

2. **Address Data Protection**
   - Encrypted at rest (AES-256-GCM)
   - Decrypted only in admin interface when needed
   - Never logged or displayed in application logs
   - Deleted after DATA_RETENTION_DAYS

3. **GDPR Compliance**
   - Address is PII → encrypted storage ✅
   - Deleted after retention period ✅
   - User can request deletion (part of order deletion) ✅
   - Minimal data collection (no phone unless needed) ✅

4. **Access Control**
   - Only admins can view decrypted addresses
   - AdminIdFilter already in place ✅
   - Consider audit logging for address access (future)

---

## 🏁 Conclusion

Phase 1 is complete with solid foundation:
- ✅ Database models ready
- ✅ Encryption working
- ✅ Validation in place
- ✅ All committed to git

Remaining phases are straightforward implementations following established patterns in the codebase. No architectural surprises expected.

**Ready for your review!** 🎉
