# Shipping Management System

**Priority:** 🟡 Medium-High
**Estimated Effort:** High (4-5 hours)
**Created:** 2025-10-23
**Branch:** `feature/shipping-management-system`

## Description

Implement a comprehensive shipping management system for physical products, including shipping cost calculation, address collection, and order fulfillment tracking.

## Requirements Summary (from discussion)

### ✅ Confirmed:
- Shipping costs defined per item in JSON import
- Shipping Address Model (**SPIKE NEEDED** for encryption/storage approach)
- New Order Status: `SHIPPED` (NOT `DELIVERED`)
- NO Tracking Numbers (never shown to users)
- Admin Interface: "Mark as Shipped" button (no tracking input)
- User Notifications when shipped
- Address Collection Flow in Checkout (**INTERVIEW MODE REQUIRED**)

### ❌ Out of Scope:
- NO Tracking Numbers
- NO `DELIVERED` status
- NO real-time tracking integration

## User Story

As a shop administrator selling physical products, I want to collect customer shipping addresses at checkout and manage order fulfillment, so that I can ship products to customers and track which orders have been shipped.

## Acceptance Criteria

### Phase 1: Shipping Cost Calculation
- [ ] JSON import format supports `shipping_cost` field per item
- [ ] Items without shipping cost default to `0.0`
- [ ] Order calculates max shipping cost: `max(item.shipping_cost for item in order_items)`
- [ ] Order model stores `shipping_cost` field separately
- [ ] Cart view displays shipping breakdown:
  - "Items: €15.00"
  - "Shipping: €5.99"
  - "Total: €20.99"
- [ ] Invoice displays shipping as separate line item

### Phase 2: Shipping Address Model (**SPIKE REQUIRED**)
- [ ] **Decision needed:** Encryption approach (GPG? AES? Field-level?)
- [ ] ShippingAddress model fields:
  - `order_id` (FK, unique)
  - `full_name` (encrypted)
  - `street_address` (encrypted)
  - `postal_code` (encrypted)
  - `city` (encrypted)
  - `country` (encrypted)
  - `phone` (optional, encrypted)
- [ ] Repository with encrypt/decrypt methods
- [ ] One address per order

### Phase 3: Address Collection Flow (**INTERVIEW MODE**)
- [ ] **Questions to discuss:**
  - When to collect address? (After crypto selection? Before invoice creation?)
  - FSM state machine flow?
  - Validation rules? (required fields, format)
  - Can user edit address after submission?
  - What if user abandons checkout after address entry?
- [ ] Multi-step form via FSM
- [ ] Validation for required fields
- [ ] Confirmation screen before order creation
- [ ] Store encrypted address with order

### Phase 4: Order Status & Workflow
- [ ] New OrderStatus: `AWAITING_SHIPMENT`
- [ ] New OrderStatus: `SHIPPED`
- [ ] Status flow:
  - `PAID` → `AWAITING_SHIPMENT` (automatic after payment)
  - `AWAITING_SHIPMENT` → `SHIPPED` (manual by admin)
- [ ] Only orders with `shipping_cost > 0` use shipping statuses
- [ ] Digital products (shipping_cost = 0) skip to delivered immediately

### Phase 5: Admin Shipping Interface
- [ ] Admin menu: "Awaiting Shipment" view
- [ ] List orders with status `AWAITING_SHIPMENT`
- [ ] Show per order:
  - Invoice number
  - Order date
  - Items
  - **Decrypted shipping address**
- [ ] "Mark as Shipped" button per order
- [ ] Confirmation dialog before marking shipped
- [ ] Paginated list

### Phase 6: User Notifications
- [ ] Notification when order status → `AWAITING_SHIPMENT`:
  - "Your order is being prepared for shipment"
- [ ] Notification when order status → `SHIPPED`:
  - "Your order has been shipped!"
  - Estimated delivery time (optional, configurable text)
- [ ] Multi-language support (DE/EN)

## Technical Notes

### JSON Import Format

```json
{
  "category": "Tea",
  "subcategory": "Green Tea",
  "price": 12.25,
  "description": "Organic Dragon Well green tea",
  "private_data": "TEA-DRAGONWELL-UNIT061",
  "shipping_cost": 1.50
}
```

### Database Changes

```python
# models/order.py
class Order(Base):
    # ... existing fields ...
    shipping_cost = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(OrderStatus), nullable=False)  # Add AWAITING_SHIPMENT, SHIPPED

# models/item.py
class Item(Base):
    # ... existing fields ...
    shipping_cost = Column(Float, nullable=False, default=0.0)

# models/shipping_address.py (NEW FILE - SPIKE NEEDED FOR ENCRYPTION)
class ShippingAddress(Base):
    __tablename__ = 'shipping_addresses'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True, nullable=False)

    # Encrypted fields (encryption method TBD in spike)
    full_name_encrypted = Column(LargeBinary, nullable=False)
    street_address_encrypted = Column(LargeBinary, nullable=False)
    postal_code_encrypted = Column(LargeBinary, nullable=False)
    city_encrypted = Column(LargeBinary, nullable=False)
    country_encrypted = Column(LargeBinary, nullable=False)
    phone_encrypted = Column(LargeBinary, nullable=True)

    created_at = Column(DateTime, default=func.now())

    # Relationship
    order = relationship("Order", back_populates="shipping_address")
```

### Encryption Spike - Options to Evaluate

**Option A: GPG (Public Key Encryption)**
- ✅ Very secure
- ✅ Admin has private key only
- ❌ Complex setup
- ❌ Requires GPG binary

**Option B: AES-256 with Key from Env**
- ✅ Simpler implementation
- ✅ Python cryptography library
- ❌ Key in .env (risk if compromised)
- ✅ Good for GDPR compliance

**Option C: Database-level Encryption**
- ✅ Transparent to application
- ❌ Requires database support (not SQLite)
- ❌ Less portable

**Recommendation:** Start with Option B (AES-256), evaluate GPG later

### Order Calculation with Shipping

```python
# In OrderService.create_order_from_cart()

# Calculate max shipping cost
max_shipping = 0.0
for cart_item in cart_items:
    item = await ItemRepository.get_single(
        cart_item.category_id,
        cart_item.subcategory_id,
        session
    )
    if item.shipping_cost > max_shipping:
        max_shipping = item.shipping_cost

# Total = items + shipping
items_total = sum(item.price * cart_item.quantity for ...)
order_total = items_total + max_shipping

# Create order with shipping
order_dto = OrderDTO(
    user_id=user_id,
    total_price=order_total,
    shipping_cost=max_shipping,
    status=OrderStatus.PENDING_PAYMENT,
    ...
)
```

### Admin "Mark as Shipped" Flow

```python
# handlers/admin/shipping.py (NEW FILE)

@shipping_router.callback_query(AdminIdFilter(), ShippingCallback.filter())
async def mark_as_shipped(callback: CallbackQuery, session: AsyncSession):
    unpacked_cb = ShippingCallback.unpack(callback.data)

    # Get order
    order = await OrderRepository.get_by_id(unpacked_cb.order_id, session)

    # Update status
    await OrderRepository.update_status(unpacked_cb.order_id, OrderStatus.SHIPPED, session)
    await session_commit(session)

    # Send user notification
    user = await UserRepository.get_by_id(order.user_id, session)
    await NotificationService.send_order_shipped_notification(user, order, session)

    await callback.answer("✅ Order marked as shipped")
```

## INTERVIEW MODE - Address Collection Flow

**Questions for discussion:**

1. **Timing:** When should we collect the shipping address?
   - Option A: Right after cart review, before crypto selection?
   - Option B: After crypto selection, before invoice creation?
   - Option C: In parallel with payment (risky - what if payment fails)?

2. **FSM States:** What states do we need?
   - `waiting_for_full_name`
   - `waiting_for_street`
   - `waiting_for_postal_code`
   - `waiting_for_city`
   - `waiting_for_country`
   - `waiting_for_phone` (optional)
   - `confirm_address`

3. **Validation:**
   - Required fields: All except phone?
   - Format validation: Postal codes by country?
   - Character limits?
   - Allow international addresses?

4. **Editability:**
   - Can user edit address after submission?
   - Can user edit address after payment?

5. **Abandonment Handling:**
   - User starts address entry, then closes chat - what happens?
   - Timeout for FSM state?
   - Clear partial data?

6. **Mixed Carts:**
   - User has both digital (no shipping) and physical (shipping) items
   - Collect address only if ANY item has shipping_cost > 0?

**Let's discuss these before implementing!**

## Localization Keys

```json
// de.json
{
  "shipping_cost": "Versandkosten",
  "total_with_shipping": "Gesamt (inkl. Versand)",
  "awaiting_shipment": "⏳ Versand wird vorbereitet",
  "shipped": "📦 Versendet",
  "order_shipped_notification": "📦 <b>Deine Bestellung wurde versendet!</b>\n\nBestellnummer: {invoice_number}\n\nDeine Bestellung ist unterwegs. Du solltest sie in den nächsten Tagen erhalten.",

  "enter_shipping_address": "📦 <b>Versandadresse</b>\n\nBitte gib deine Versandadresse ein.",
  "enter_full_name": "👤 Bitte gib deinen vollständigen Namen ein:",
  "enter_street_address": "🏠 Bitte gib deine Straße und Hausnummer ein:",
  "enter_postal_code": "📮 Bitte gib deine Postleitzahl ein:",
  "enter_city": "🏙️ Bitte gib deine Stadt ein:",
  "enter_country": "🌍 Bitte gib dein Land ein:",
  "enter_phone_optional": "📱 Bitte gib deine Telefonnummer ein (optional):",
  "confirm_address": "✅ <b>Bestätige deine Versandadresse:</b>\n\n{full_name}\n{street}\n{postal_code} {city}\n{country}\n\nIst diese Adresse korrekt?",

  "admin_awaiting_shipment_list": "📦 <b>Bestellungen warten auf Versand</b>\n\nAnzahl: {count}",
  "admin_mark_as_shipped": "✅ Als versendet markieren"
}

// en.json
{
  "shipping_cost": "Shipping Cost",
  "total_with_shipping": "Total (incl. Shipping)",
  "awaiting_shipment": "⏳ Awaiting Shipment",
  "shipped": "📦 Shipped",
  "order_shipped_notification": "📦 <b>Your order has been shipped!</b>\n\nOrder number: {invoice_number}\n\nYour order is on its way. You should receive it in the next few days.",

  "enter_shipping_address": "📦 <b>Shipping Address</b>\n\nPlease enter your shipping address.",
  "enter_full_name": "👤 Please enter your full name:",
  "enter_street_address": "🏠 Please enter your street and house number:",
  "enter_postal_code": "📮 Please enter your postal code:",
  "enter_city": "🏙️ Please enter your city:",
  "enter_country": "🌍 Please enter your country:",
  "enter_phone_optional": "📱 Please enter your phone number (optional):",
  "confirm_address": "✅ <b>Confirm your shipping address:</b>\n\n{full_name}\n{street}\n{postal_code} {city}\n{country}\n\nIs this address correct?",

  "admin_awaiting_shipment_list": "📦 <b>Orders Awaiting Shipment</b>\n\nCount: {count}",
  "admin_mark_as_shipped": "✅ Mark as Shipped"
}
```

## Implementation Order

1. **SPIKE:** Research and decide on encryption approach (1-2 hours)
2. **INTERVIEW:** Design address collection flow (30 min discussion)
3. Database models (Item.shipping_cost, Order.shipping_cost, ShippingAddress)
4. JSON import support for shipping_cost
5. Shipping cost calculation in OrderService
6. Cart display with shipping breakdown
7. Address collection FSM flow
8. Address encryption/storage
9. New order statuses (AWAITING_SHIPMENT, SHIPPED)
10. Admin shipping management interface
11. "Mark as Shipped" functionality
12. User notifications
13. Testing with physical products

## Testing Checklist

- [ ] Import items with various shipping costs
- [ ] Order with single item (shipping = item shipping cost)
- [ ] Order with multiple items (shipping = max cost)
- [ ] Order with mixed digital/physical items
- [ ] Address collection flow (happy path)
- [ ] Address validation errors
- [ ] Address encryption/decryption
- [ ] Admin can view encrypted addresses
- [ ] Admin can mark orders as shipped
- [ ] User receives shipped notification
- [ ] Order status transitions correctly

## Security & Privacy

**Encryption:**
- All shipping addresses MUST be encrypted at rest
- Decryption only in admin interface when needed
- Never log or display unencrypted addresses in application logs

**Data Retention:**
- Shipping addresses deleted with order after DATA_RETENTION_DAYS
- Consider shorter retention for addresses specifically?

**GDPR Compliance:**
- Collect only necessary address fields
- Inform user why address is needed
- Allow user to request address deletion (part of order deletion)

## Related

- Requires: Database migration for new fields
- Enhances: Order system with physical product support
- Integrates: Admin panel for fulfillment
- Affects: Cart display, Order creation flow
