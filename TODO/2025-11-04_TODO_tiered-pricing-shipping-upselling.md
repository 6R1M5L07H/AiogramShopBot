# Tiered Pricing, Dynamic Shipping & Upselling System

**Date:** 2025-11-04
**Priority:** High
**Estimated Effort:** Very High (12-16 hours)

---

## Description
Comprehensive pricing and upselling system combining three major features:

1. **Tiered Pricing**: Automatic price optimization based on quantity (e.g., 17 items → 10×9€ + 5×10€ + 2×11€)
2. **Dynamic Shipping Tiers**: Quantity-dependent shipping methods with insurance upsells
3. **Item-Level Upsells**: Optional add-ons like premium packaging (frustration-free, gift wrapping)
4. **Customer Status System**: First-time buyers vs. returning customers with different insurance benefits

This system eliminates pre-packaged bundles, provides transparent pricing, and enables flexible upselling while maintaining customer trust through insurance guarantees.

---

## Business Goals

### Problem Statement
Currently, shop owners must pre-package items into fixed bundles (e.g., 10×100-packs, 5×20-packs) without knowing customer demand. This creates:
- Inventory inflexibility
- Missed sales opportunities
- Poor customer experience (forced to buy unwanted quantities)

### Solution
Dynamic pricing and shipping system that:
- Calculates optimal price for ANY quantity
- Adjusts shipping method based on quantity
- Offers transparent upsells (packaging, insurance)
- Rewards customer loyalty with better insurance terms

### Key Benefits
- **For Customers**: Transparent pricing, flexible quantities, visible savings incentives
- **For Shop Owner**: Increased AOV through upselling, better inventory management, reduced support load

---

## Business Example: USB-Sticks

**Configuration:**
- Stock: 100 units
- Price Tiers: 1-4 (€11), 5-9 (€10), 10-24 (€9), 25-49 (€8), 50+ (€7)
- Shipping Tiers:
  - 1-5 units: Warensendung (€0.00) or Einschreiben (+€2.50)
  - 6-20 units: Päckchen (€0.00) or Paket Klein Versichert (+€3.50)
  - 21+ units: Paket Mittel (€0.00) or Paket Mittel Versichert (+€4.50)
- Upsells: Frustration-free packaging (+€4.00)

**Customer Journey:**
1. Customer selects 17 units
2. System calculates optimal price:
   ```
   10 ×  9,00 €  =   90,00 €
    5 × 10,00 €  =   50,00 €
    2 × 11,00 €  =   22,00 €
   ─────────────────────────────
   17 × USB-Stick = 162,00 €
   Ø 9,53 €/unit
   ```
3. Upselling screen shows:
   - Frustration-free packaging: +€4.00
   - Insured shipping (Paket Klein): +€3.50
   - Customer status: "Als Erstkäufer: 50% Refund bei Verlust"
4. Customer sees incentive: "Buy 20 units for only €18 more (Ø €9.00/unit)!"

---

## User Stories

### US-1: Tiered Pricing
As a shop administrator, I want to configure price tiers so that customers automatically get the best price for any quantity they choose.

### US-2: Dynamic Shipping
As a shop administrator, I want shipping costs to adjust based on order quantity so that small orders use cheaper methods and large orders use appropriate packaging.

### US-3: Insurance Upselling
As a shop administrator, I want to offer insured shipping as an upsell so that customers can choose protection while I increase revenue.

### US-4: Item Upsells
As a shop administrator, I want to offer optional add-ons like premium packaging so that customers can customize their purchase and I can increase AOV.

### US-5: Customer Loyalty
As a returning customer, I want better insurance terms (full re-shipment vs. 50% refund) as a reward for my loyalty.

### US-6: Quick Checkout
As a customer, I want a direct checkout button after adding items to cart so that I can complete my purchase faster.

---

## Acceptance Criteria

### Core Pricing System
- [ ] JSON import supports `price_tiers` array with `min_quantity` and `unit_price`
- [ ] Backwards compatible: Items without `price_tiers` use legacy `price` field
- [ ] System calculates optimal tier combination using greedy algorithm
- [ ] Cart displays transparent breakdown of tier calculation
- [ ] Average unit price displayed for customer reference

### Dynamic Shipping System
- [ ] Global `SHIPPING_TYPES` configuration in `config.py`
- [ ] JSON import supports `shipping_tiers` array with quantity ranges
- [ ] Each tier references `standard_type` and optional `insured_available`
- [ ] Shipping cost explicitly shown as €0.00 for standard methods
- [ ] Order-level shipping uses Max-Prinzip (highest tier wins)
- [ ] Mixed orders (physical + digital) only calculate shipping for physical items
- [ ] Packstation availability = AND logic (all items must allow it)

### Upselling System
- [ ] Global `UPSELL_OPTIONS` configuration in `config.py`
- [ ] Items reference available upsells by ID (e.g., `["frustfree_packaging"]`)
- [ ] Upselling screen shown after quantity selection, before cart
- [ ] Toggle buttons show current state: `[✓ Frustfrei +4,00 €]` or `[○ Frustfrei +4,00 €]`
- [ ] Item-level upsells (packaging) stored per cart item
- [ ] Order-level upsells (shipping insurance) apply to entire order
- [ ] Real-time total update when toggling upsells
- [ ] No dependencies between upsells (all combinations allowed)

### Customer Status System
- [ ] New table `user_order_stats` tracks order counts per user
- [ ] Status determined by `paid_and_shipped_orders` (configurable threshold)
- [ ] `paid_and_shipped_orders` auto-incremented when admin marks order as shipped
- [ ] Digital goods increment `paid_orders` but NOT `paid_and_shipped_orders`
- [ ] User profile displays customer status and benefits
- [ ] Upselling screen shows personalized insurance benefits
- [ ] Configurable thresholds in `config.py`

### UX Enhancements
- [ ] After adding to cart, show `[🛒 Warenkorb] [✅ Zur Kasse] [⬅️ Weiter shoppen]`
- [ ] Upselling screen shows beautiful tier breakdown with aligned formatting
- [ ] Status indicator in user profile: 🏆 STATUS: Bestandskunde ✓
- [ ] Insurance benefits explained clearly in upselling screen

---

## Technical Implementation

### 1. Global Configuration (`config.py`)

```python
# ============================================
# VERSANDTYPEN (Shipping Types)
# ============================================
SHIPPING_TYPES = {
    # Standard (gratis in Produktpreis enthalten)
    "warensendung": {
        "name_key": "shipping_warensendung",
        "base_cost": 0.00,
        "allows_packstation": False,
        "has_tracking": False,
        "max_weight_grams": 500,
        "insured_upgrade": "einschreiben"
    },
    "paeckchen": {
        "name_key": "shipping_paeckchen",
        "base_cost": 0.00,
        "allows_packstation": True,
        "has_tracking": False,
        "max_weight_grams": 2000,
        "insured_upgrade": "paket_klein_versichert"
    },
    "paket_klein": {
        "name_key": "shipping_paket_klein",
        "base_cost": 0.00,
        "allows_packstation": True,
        "has_tracking": False,
        "max_weight_grams": 10000,
        "insured_upgrade": "paket_klein_versichert"
    },
    "paket_mittel": {
        "name_key": "shipping_paket_mittel",
        "base_cost": 0.00,
        "allows_packstation": True,
        "has_tracking": False,
        "max_weight_grams": 31500,
        "insured_upgrade": "paket_mittel_versichert"
    },

    # Versichert (Upsell - relativer Aufpreis)
    "einschreiben": {
        "name_key": "shipping_einschreiben",
        "base_cost": 2.50,
        "allows_packstation": False,
        "has_tracking": True,
        "insurance_type": "basic",
        "insured_upgrade": None
    },
    "paket_klein_versichert": {
        "name_key": "shipping_paket_klein_insured",
        "base_cost": 3.50,
        "allows_packstation": True,
        "has_tracking": True,
        "insurance_type": "full",
        "insured_upgrade": None
    },
    "paket_mittel_versichert": {
        "name_key": "shipping_paket_mittel_insured",
        "base_cost": 4.50,
        "allows_packstation": True,
        "has_tracking": True,
        "insurance_type": "full",
        "insured_upgrade": None
    }
}

# ============================================
# UPSELL-OPTIONEN (Item-Level Add-ons)
# ============================================
UPSELL_OPTIONS = {
    "frustfree_packaging": {
        "name_key": "upsell_frustfree_packaging",
        "description_key": "upsell_frustfree_packaging_desc",
        "cost": 4.00,
        "type": "packaging",
        "applies_to": ["physical"]
    },
    "gift_wrapping": {
        "name_key": "upsell_gift_wrapping",
        "description_key": "upsell_gift_wrapping_desc",
        "cost": 2.50,
        "type": "packaging",
        "applies_to": ["physical"]
    }
}

# ============================================
# VERSICHERUNGS-GARANTIEN
# ============================================
SHIPPING_INSURANCE = {
    "returning_customer_threshold": 3,
    "returning_customer_requires_shipment": True,
    "first_buyer_refund_percentage": 50,
    "returning_customer_policy": "full_reship"
}
```

### 2. JSON Format

**USB-Sticks with Full Configuration:**
```json
{
  "category": "Computer Zubehör",
  "subcategory": "USB-Sticks",
  "description": "SanDisk 32GB USB 3.0",
  "private_data": "USB-SANDISK-32GB-{001-100}",
  "is_physical": true,

  "price_tiers": [
    {"min_quantity": 1, "unit_price": 11.00},
    {"min_quantity": 5, "unit_price": 10.00},
    {"min_quantity": 10, "unit_price": 9.00},
    {"min_quantity": 25, "unit_price": 8.00},
    {"min_quantity": 50, "unit_price": 7.00}
  ],

  "shipping_tiers": [
    {
      "min_quantity": 1,
      "max_quantity": 5,
      "standard_type": "warensendung",
      "insured_available": true
    },
    {
      "min_quantity": 6,
      "max_quantity": 20,
      "standard_type": "paeckchen",
      "insured_available": true
    },
    {
      "min_quantity": 21,
      "max_quantity": null,
      "standard_type": "paket_mittel",
      "insured_available": true
    }
  ],

  "available_upsells": [
    "frustfree_packaging",
    "gift_wrapping"
  ]
}
```

**Backwards Compatible (Legacy Format):**
```json
{
  "category": "Beratung",
  "subcategory": "IT-Beratung",
  "description": "0,25h IT-Beratung",
  "private_data": "CONSULTING-QUARTER-HOUR-{001-200}",
  "is_physical": false,
  "price": 30.00
}
```
→ Auto-converted to single tier: `[{"min_quantity": 1, "unit_price": 30.00}]`

### 3. Database Schema

#### New Table: `price_tiers`
```sql
CREATE TABLE price_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX idx_price_tiers_item_id ON price_tiers(item_id);
```

#### New Table: `shipping_tiers`
```sql
CREATE TABLE shipping_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
    max_quantity INTEGER NULL,  -- NULL = infinity
    standard_type VARCHAR(50) NOT NULL,  -- Reference to SHIPPING_TYPES
    insured_available BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX idx_shipping_tiers_item_id ON shipping_tiers(item_id);
```

#### New Table: `item_upsells`
```sql
CREATE TABLE item_upsells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    upsell_key VARCHAR(50) NOT NULL,  -- Reference to UPSELL_OPTIONS
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX idx_item_upsells_item_id ON item_upsells(item_id);
```

#### New Table: `user_order_stats`
```sql
CREATE TABLE user_order_stats (
    user_id INTEGER PRIMARY KEY,
    total_orders INTEGER DEFAULT 0,
    paid_orders INTEGER DEFAULT 0,
    paid_and_shipped_orders INTEGER DEFAULT 0,
    customer_status VARCHAR(20) DEFAULT 'new',  -- 'new', 'returning'
    last_updated DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_order_stats_status ON user_order_stats(customer_status);
```

#### Updated Table: `cart_items`
```sql
ALTER TABLE cart_items ADD COLUMN selected_upsells TEXT;  -- JSON: ["frustfree_packaging"]
ALTER TABLE cart_items ADD COLUMN upsell_total REAL DEFAULT 0.0;
```

#### New Table: `order_shipping`
```sql
CREATE TABLE order_shipping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    shipping_type VARCHAR(50) NOT NULL,
    is_insured BOOLEAN DEFAULT FALSE,
    shipping_cost REAL NOT NULL,
    allows_packstation BOOLEAN NOT NULL,
    tracking_number VARCHAR(100) NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE INDEX idx_order_shipping_order_id ON order_shipping(order_id);
```

#### Migration Strategy
1. Create all new tables
2. Migrate existing items:
   - `Item.price` → single tier in `price_tiers`
   - `Item.shipping_cost` → single tier in `shipping_tiers` (if `is_physical`)
3. Initialize `user_order_stats` from existing order data
4. Keep legacy columns for backwards compatibility (do NOT drop)

### 4. Repository Layer

#### New: `PriceTierRepository`
```python
class PriceTierRepository:
    @staticmethod
    async def get_by_item_id(item_id: int, session: AsyncSession | Session) -> list[PriceTier]:
        """Get all price tiers for an item, sorted by min_quantity ASC."""
        pass

    @staticmethod
    async def add_many(tiers: list[PriceTierDTO], session: AsyncSession | Session) -> None:
        """Bulk insert price tiers for an item."""
        pass

    @staticmethod
    async def delete_by_item_id(item_id: int, session: AsyncSession | Session) -> None:
        """Delete all tiers for an item (used during re-import)."""
        pass
```

#### New: `ShippingTierRepository`
```python
class ShippingTierRepository:
    @staticmethod
    async def get_by_item_id(item_id: int, session: AsyncSession | Session) -> list[ShippingTier]:
        pass

    @staticmethod
    async def get_tier_for_quantity(
        item_id: int,
        quantity: int,
        session: AsyncSession | Session
    ) -> ShippingTier:
        """Find matching tier where min_quantity <= quantity <= max_quantity."""
        pass
```

#### New: `ItemUpsellRepository`
```python
class ItemUpsellRepository:
    @staticmethod
    async def get_by_item_id(item_id: int, session: AsyncSession | Session) -> list[str]:
        """Returns list of upsell_keys for an item."""
        pass
```

#### New: `UserOrderStatsRepository`
```python
class UserOrderStatsRepository:
    @staticmethod
    async def get_or_create(user_id: int, session: AsyncSession | Session) -> UserOrderStats:
        pass

    @staticmethod
    async def increment_paid_order(user_id: int, session: AsyncSession | Session) -> None:
        """Called when order payment is confirmed."""
        pass

    @staticmethod
    async def increment_shipped_order(user_id: int, session: AsyncSession | Session) -> None:
        """Called when admin marks order as shipped (only for physical goods)."""
        pass

    @staticmethod
    async def update_status(user_id: int, session: AsyncSession | Session) -> None:
        """Recalculate customer status based on thresholds."""
        pass
```

### 5. Service Layer

#### New: `PricingService`
```python
class PricingService:
    @staticmethod
    async def calculate_optimal_price(
        subcategory_id: int,
        quantity: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Calculate optimal tier combination using greedy algorithm.

        Returns:
            {
                "total": 162.00,
                "average_unit_price": 9.53,
                "breakdown": [
                    {"quantity": 10, "unit_price": 9.00, "total": 90.00},
                    {"quantity": 5, "unit_price": 10.00, "total": 50.00},
                    {"quantity": 2, "unit_price": 11.00, "total": 22.00}
                ]
            }
        """
        # Get sample item from subcategory
        sample_item = await ItemRepository.get_one_by_subcategory(subcategory_id, session)
        tiers = await PriceTierRepository.get_by_item_id(sample_item.id, session)

        # Sort tiers by min_quantity DESC (largest first)
        sorted_tiers = sorted(tiers, key=lambda t: t.min_quantity, reverse=True)

        breakdown = []
        remaining = quantity

        for tier in sorted_tiers:
            if remaining >= tier.min_quantity:
                tier_count = remaining // tier.min_quantity
                tier_quantity = tier_count * tier.min_quantity

                breakdown.append({
                    "quantity": tier_quantity,
                    "unit_price": tier.unit_price,
                    "total": tier_quantity * tier.unit_price
                })

                remaining -= tier_quantity

        # Handle remaining units with smallest tier
        if remaining > 0:
            smallest_tier = sorted_tiers[-1]
            breakdown.append({
                "quantity": remaining,
                "unit_price": smallest_tier.unit_price,
                "total": remaining * smallest_tier.unit_price
            })

        total = sum(item["total"] for item in breakdown)
        average_unit_price = total / quantity

        return {
            "total": total,
            "average_unit_price": average_unit_price,
            "breakdown": breakdown
        }
```

#### New: `ShippingService`
```python
class ShippingService:
    @staticmethod
    async def calculate_order_shipping(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> dict:
        """
        Calculate shipping for entire order using Max-Prinzip.
        Only considers physical items.

        Returns:
            {
                "standard": {
                    "type": "paket_klein",
                    "cost": 0.00,
                    "allows_packstation": True,
                    "name": "Kleines Paket"
                },
                "insured": {
                    "type": "paket_klein_versichert",
                    "cost": 3.50,
                    "allows_packstation": True,
                    "available": True,
                    "name": "Kleines Paket (Versichert)"
                },
                "breakdown": [
                    {
                        "subcategory": "USB-Sticks",
                        "quantity": 17,
                        "is_physical": True,
                        "shipping_tier": "paeckchen"
                    },
                    {
                        "subcategory": "IT-Beratung",
                        "quantity": 2,
                        "is_physical": False,
                        "shipping_tier": None
                    }
                ]
            }
        """
        physical_items = []
        breakdown = []

        for cart_item in cart_items:
            # Get sample item to check if physical
            sample_item = await ItemRepository.get_one_by_subcategory(
                cart_item.subcategory_id, session
            )

            is_physical = sample_item.is_physical
            shipping_tier = None

            if is_physical:
                shipping_tier_obj = await ShippingTierRepository.get_tier_for_quantity(
                    sample_item.id, cart_item.quantity, session
                )
                shipping_tier = shipping_tier_obj.standard_type
                physical_items.append({
                    "tier": shipping_tier_obj,
                    "quantity": cart_item.quantity
                })

            breakdown.append({
                "subcategory": cart_item.subcategory_name,
                "quantity": cart_item.quantity,
                "is_physical": is_physical,
                "shipping_tier": shipping_tier
            })

        if not physical_items:
            # No physical items, no shipping
            return {
                "standard": None,
                "insured": None,
                "breakdown": breakdown
            }

        # Apply Max-Prinzip for standard shipping
        max_standard_type = None
        max_standard_cost = 0.0
        allows_packstation = True
        insured_available = False

        for item in physical_items:
            tier_config = SHIPPING_TYPES[item["tier"].standard_type]

            if tier_config["base_cost"] > max_standard_cost:
                max_standard_cost = tier_config["base_cost"]
                max_standard_type = item["tier"].standard_type

            # AND logic for packstation
            if not tier_config["allows_packstation"]:
                allows_packstation = False

            # OR logic for insured availability
            if item["tier"].insured_available:
                insured_available = True

        standard_config = SHIPPING_TYPES[max_standard_type]

        # Calculate insured option
        insured = None
        if insured_available and standard_config["insured_upgrade"]:
            insured_type = standard_config["insured_upgrade"]
            insured_config = SHIPPING_TYPES[insured_type]

            insured = {
                "type": insured_type,
                "cost": insured_config["base_cost"],
                "allows_packstation": insured_config["allows_packstation"],
                "available": True,
                "name": Localizator.get_text(BotEntity.USER, insured_config["name_key"])
            }

        return {
            "standard": {
                "type": max_standard_type,
                "cost": max_standard_cost,
                "allows_packstation": allows_packstation,
                "name": Localizator.get_text(BotEntity.USER, standard_config["name_key"])
            },
            "insured": insured,
            "breakdown": breakdown
        }

    @staticmethod
    async def get_user_insurance_benefits(
        user_id: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Get user's insurance benefits based on order history.

        Returns:
            {
                "status": "returning",
                "paid_orders": 8,
                "paid_and_shipped": 6,
                "threshold": 3,
                "refund_percentage": 100,
                "policy": "full_reship",
                "benefits": [
                    "Volle Neulieferung bei Verlust",
                    "Prioritäts-Support"
                ]
            }
        """
        stats = await UserOrderStatsRepository.get_or_create(user_id, session)

        threshold = SHIPPING_INSURANCE["returning_customer_threshold"]
        is_returning = stats.paid_and_shipped_orders >= threshold

        if is_returning:
            refund_pct = 100
            policy = SHIPPING_INSURANCE["returning_customer_policy"]
            benefits = [
                "full_reship_guarantee",
                "priority_support",
                "early_access"
            ]
        else:
            refund_pct = SHIPPING_INSURANCE["first_buyer_refund_percentage"]
            policy = "partial_refund"
            benefits = ["partial_refund_guarantee"]

        return {
            "status": "returning" if is_returning else "new",
            "paid_orders": stats.paid_orders,
            "paid_and_shipped": stats.paid_and_shipped_orders,
            "threshold": threshold,
            "refund_percentage": refund_pct,
            "policy": policy,
            "benefits": benefits
        }
```

#### New: `UpsellService`
```python
class UpsellService:
    @staticmethod
    async def get_available_upsells(
        item_id: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Get available upsells for an item.

        Returns:
            {
                "item_upsells": [
                    {
                        "key": "frustfree_packaging",
                        "name": "Frustfreie Verpackung",
                        "description": "...",
                        "cost": 4.00,
                        "type": "packaging"
                    }
                ],
                "total_cost": 6.50
            }
        """
        upsell_keys = await ItemUpsellRepository.get_by_item_id(item_id, session)

        upsells = []
        for key in upsell_keys:
            config = UPSELL_OPTIONS[key]
            upsells.append({
                "key": key,
                "name": Localizator.get_text(BotEntity.USER, config["name_key"]),
                "description": Localizator.get_text(BotEntity.USER, config["description_key"]),
                "cost": config["cost"],
                "type": config["type"]
            })

        return {
            "item_upsells": upsells,
            "total_cost": sum(u["cost"] for u in upsells)
        }
```

#### Updated: `CartService`
```python
class CartService:
    @staticmethod
    async def add_to_cart(...) -> tuple[bool, str, dict, bool]:
        """
        CHANGED: Now returns show_checkout_button flag.

        Returns:
            (success, message_key, format_args, show_checkout_button)
        """
        # ... existing logic ...

        return True, "item_added_to_cart", {}, True  # Always show checkout button

    @staticmethod
    async def calculate_cart_total(
        user_id: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Calculate complete cart total with tiered pricing, upsells, and shipping.

        Returns:
            {
                "items": [
                    {
                        "subcategory_name": "USB-Sticks",
                        "quantity": 17,
                        "pricing": {...},  # from PricingService
                        "upsells": ["frustfree_packaging"],
                        "upsell_total": 4.00
                    }
                ],
                "subtotal": 162.00,
                "upsells_total": 4.00,
                "shipping": {...},  # from ShippingService
                "shipping_selected": "insured",  # or "standard"
                "shipping_cost": 3.50,
                "grand_total": 169.50
            }
        """
        pass
```

#### Updated: `OrderService`
```python
class OrderService:
    @staticmethod
    async def mark_as_shipped(
        order_id: int,
        tracking_number: str,
        session: AsyncSession | Session
    ) -> None:
        """
        CHANGED: Now updates user_order_stats.
        """
        order = await OrderRepository.get_by_id(order_id, session)

        # Update order status
        order.status = OrderStatus.SHIPPED

        # Update shipping record
        shipping = await OrderShippingRepository.get_by_order_id(order_id, session)
        shipping.tracking_number = tracking_number

        # Check if order contains physical items
        has_physical = await OrderService._has_physical_items(order_id, session)

        if has_physical:
            # Increment user's shipped order count
            await UserOrderStatsRepository.increment_shipped_order(order.user_id, session)
            await UserOrderStatsRepository.update_status(order.user_id, session)

        await session_commit(session)
```

### 6. UI/UX Implementation

#### Upselling Screen Handler

```python
class UpsellHandler:
    @router.callback_query(UpsellCallback.filter())
    async def handle_upsell_toggle(
        callback: CallbackQuery,
        session: AsyncSession
    ):
        """Handle upsell toggle button clicks."""
        cb = UpsellCallback.unpack(callback.data)

        # Get current state from FSM or temp storage
        state_data = await state.get_data()
        selected_upsells = state_data.get("selected_upsells", [])
        selected_shipping = state_data.get("selected_shipping", "standard")

        if cb.action == "toggle_item":
            # Toggle item upsell
            if cb.upsell_id in selected_upsells:
                selected_upsells.remove(cb.upsell_id)
            else:
                selected_upsells.append(cb.upsell_id)

        elif cb.action == "toggle_shipping":
            # Toggle shipping insurance
            selected_shipping = "insured" if selected_shipping == "standard" else "standard"

        # Update state
        await state.update_data(
            selected_upsells=selected_upsells,
            selected_shipping=selected_shipping
        )

        # Regenerate message with updated totals
        message = await UpsellService.generate_upsell_message(
            subcategory_id=cb.subcategory_id,
            quantity=cb.quantity,
            selected_upsells=selected_upsells,
            selected_shipping=selected_shipping,
            user_id=callback.from_user.id,
            session=session
        )

        await callback.message.edit_text(
            message["text"],
            reply_markup=message["keyboard"]
        )
```

#### Upselling Screen Message Format

```
═══════════════════════════════════
USB-Stick SanDisk 32GB
Menge: 17 Stück

Staffelpreise:
 10 ×  9,00 €  =   90,00 €
  5 × 10,00 €  =   50,00 €
  2 × 11,00 €  =   22,00 €
───────────────────────────────────
              Σ  162,00 €
              Ø    9,53 €/Stk.

═══════════════════════════════════

📦 VERPACKUNG (optional)

[○ Frustfrei +4,00 €]
[○ Geschenkverpackung +2,50 €]

🚚 VERSAND

Standard: Päckchen (0,00 €)
Kein Tracking, Risiko beim Käufer

[○ Versichert (+3,50 €)]
   Mit Tracking & Garantie 🛡️

   Als Erstkäufer erhältst du:
   • 50% Refund bei Verlust

   Ab 3 bezahlten Bestellungen:
   • Volle Neulieferung bei Verlust
   • Prioritäts-Support

───────────────────────────────────
GESAMT: 162,00 €
═══════════════════════════════════

[✓ In Warenkorb] [✗ Abbrechen]
```

#### User Profile Display

```
═══════════════════════════════════
👤 DEIN PROFIL

Name: Max Mustermann
Telegram: @maxmuster
User-ID: 123456

💰 Guthaben: 50,00 €

📦 BESTELLHISTORIE
Gesamt: 12 Bestellungen
Bezahlt: 8 Bestellungen
Versendet: 6 Bestellungen

🏆 STATUS: Bestandskunde ✓
   ├─ 50% Refund-Garantie ✗
   └─ Volle Neulieferungs-Garantie ✓

Vorteile als Bestandskunde:
• Volle Neulieferung bei Verlust
• Prioritäts-Support
• Frühzugang zu neuen Produkten

═══════════════════════════════════

[💳 Guthaben aufladen]
[📋 Bestellungen ansehen]
[⬅️ Zurück]
```

### 7. Localization Keys

Add to `l10n/de.json`:

```json
{
  "shipping_warensendung": "Warensendung",
  "shipping_paeckchen": "Päckchen",
  "shipping_paket_klein": "Kleines Paket",
  "shipping_paket_mittel": "Mittleres Paket",
  "shipping_einschreiben": "Einschreiben (Versichert)",
  "shipping_paket_klein_insured": "Kleines Paket (Versichert)",
  "shipping_paket_mittel_insured": "Mittleres Paket (Versichert)",

  "upsell_frustfree_packaging": "Frustfreie Verpackung",
  "upsell_frustfree_packaging_desc": "Leicht zu öffnende, umweltfreundliche Verpackung",
  "upsell_gift_wrapping": "Geschenkverpackung",
  "upsell_gift_wrapping_desc": "Hochwertige Geschenkverpackung mit Schleife",

  "customer_status_new": "Erstkäufer",
  "customer_status_returning": "Bestandskunde",
  "insurance_benefit_partial_refund": "50% Refund bei Verlust",
  "insurance_benefit_full_reship": "Volle Neulieferung bei Verlust",
  "insurance_benefit_priority_support": "Prioritäts-Support",
  "insurance_benefit_early_access": "Frühzugang zu neuen Produkten",

  "upsell_screen_title": "Optionen auswählen",
  "upsell_packaging_section": "📦 VERPACKUNG (optional)",
  "upsell_shipping_section": "🚚 VERSAND",
  "upsell_total": "GESAMT: {total:.2f} €",
  "upsell_add_to_cart": "✓ In Warenkorb",
  "upsell_cancel": "✗ Abbrechen"
}
```

---

## Testing Strategy

### Unit Tests

#### `tests/pricing/unit/test_pricing_service.py`
```python
@pytest.mark.asyncio
async def test_calculate_optimal_price_exact_tier():
    """Test price calculation when quantity matches tier exactly."""
    # 10 items → should use 10×9€ tier
    result = await PricingService.calculate_optimal_price(
        subcategory_id=1, quantity=10, session=session
    )
    assert result["total"] == 90.00
    assert result["average_unit_price"] == 9.00
    assert len(result["breakdown"]) == 1

@pytest.mark.asyncio
async def test_calculate_optimal_price_mixed_tiers():
    """Test price calculation with multiple tiers."""
    # 17 items → 10×9€ + 5×10€ + 2×11€
    result = await PricingService.calculate_optimal_price(
        subcategory_id=1, quantity=17, session=session
    )
    assert result["total"] == 162.00
    assert result["average_unit_price"] == pytest.approx(9.53, rel=0.01)
    assert len(result["breakdown"]) == 3
```

#### `tests/shipping/unit/test_shipping_service.py`
```python
@pytest.mark.asyncio
async def test_max_prinzip_shipping():
    """Test Max-Prinzip for mixed cart."""
    cart_items = [
        CartItemDTO(subcategory_id=1, quantity=5),   # Warensendung
        CartItemDTO(subcategory_id=2, quantity=15)   # Paket Klein
    ]
    result = await ShippingService.calculate_order_shipping(cart_items, session)

    assert result["standard"]["type"] == "paket_klein"
    assert result["standard"]["cost"] == 0.00

@pytest.mark.asyncio
async def test_packstation_and_logic():
    """Test Packstation availability with AND logic."""
    # Mix: Warensendung (no packstation) + Paket (packstation)
    cart_items = [
        CartItemDTO(subcategory_id=1, quantity=3),   # Warensendung
        CartItemDTO(subcategory_id=2, quantity=10)   # Paket
    ]
    result = await ShippingService.calculate_order_shipping(cart_items, session)

    assert result["standard"]["allows_packstation"] == False  # AND logic
```

### Manual Tests

#### `tests/upselling/manual/test_upsell_flow.py`
```python
"""
Manual test for upselling flow:

1. Start bot
2. Select USB-Stick category
3. Enter quantity: 17
4. Verify upselling screen appears
5. Toggle "Frustfreie Verpackung"
6. Verify total updates: 162€ → 166€
7. Toggle "Versichert"
8. Verify total updates: 166€ → 169.50€
9. Add to cart
10. Verify cart shows all selections
"""
```

### Integration Tests

#### `tests/integration/test_order_flow_with_upsells.py`
```python
@pytest.mark.asyncio
async def test_complete_order_flow_with_upsells():
    """Test complete order flow with tiered pricing and upsells."""
    # 1. Add item to cart with upsells
    # 2. Calculate shipping (insured)
    # 3. Create order
    # 4. Complete payment
    # 5. Verify order_shipping record
    # 6. Mark as shipped
    # 7. Verify user_order_stats updated
    pass
```

---

## Dependencies

### Technical Dependencies
- Alembic migration for 5 new tables + 2 altered tables
- Data migration for existing items (price → price_tiers)
- JSON importer changes (handle new fields)
- Localization keys (30+ new keys)

### Feature Dependencies
- Requires working cart system ✓
- Requires order system ✓
- Requires payment system ✓
- Requires admin order management ✓

### External Dependencies
- None (all features are self-contained)

---

## Rollout Strategy

### Phase 1: Database & Data Migration (Day 1)
- [ ] Create Alembic migration
- [ ] Run migration on dev database
- [ ] Migrate existing items to new schema
- [ ] Verify data integrity

### Phase 2: Core Services (Day 2-3)
- [ ] Implement `PricingService`
- [ ] Implement `ShippingService`
- [ ] Implement `UpsellService`
- [ ] Unit tests for all services

### Phase 3: Repositories (Day 3-4)
- [ ] Implement all new repositories
- [ ] Update existing repositories (CartRepository, OrderRepository)
- [ ] Integration tests

### Phase 4: UI/UX (Day 4-5)
- [ ] Implement upselling screen handler
- [ ] Update cart display
- [ ] Update user profile
- [ ] Add localization keys

### Phase 5: Order Flow Integration (Day 5-6)
- [ ] Update order creation with shipping/upsells
- [ ] Update admin order management (mark as shipped)
- [ ] Update invoice generation
- [ ] End-to-end tests

### Phase 6: JSON Import (Day 6)
- [ ] Update JSON importer
- [ ] Test with sample data
- [ ] Create migration guide for admins

### Phase 7: Testing & Polish (Day 7)
- [ ] Manual testing
- [ ] Bug fixes
- [ ] Performance optimization
- [ ] Documentation

### Phase 8: Production Deployment (Day 8)
- [ ] Deploy to production
- [ ] Monitor logs
- [ ] User feedback
- [ ] Hotfixes if needed

---

## Future Enhancements (Out of Scope)

- [ ] Incentive messaging: "Buy X more to save €Y!" (requires additional BI logic)
- [ ] Dynamic tier suggestions based on demand analytics
- [ ] A/B testing for upsell conversion rates
- [ ] Admin UI for editing tiers via Telegram bot
- [ ] Tier-based quantity quick-select buttons (e.g., [1x] [5x] [10x])
- [ ] Gift messages for gift wrapping upsell
- [ ] Express delivery tracking integration
- [ ] Customer loyalty program (points system)
- [ ] Seasonal tier promotions

---

## Risk Assessment

### High Risk
- **Callback data size limit**: Telegram has 64-byte limit. Use compressed encoding.
- **Performance**: N+1 queries when loading cart. Use eager loading with JOINs.
- **Data consistency**: Upsells might be deleted after cart item created. Store full data in JSON.

### Medium Risk
- **User confusion**: Complex tier breakdown might overwhelm users. Solution: Clear UI, hide complexity.
- **Migration errors**: Existing items need careful migration. Solution: Thorough testing on dev first.

### Low Risk
- **Localization**: Many new keys needed. Solution: Start with German, add English later.

---

## Success Metrics

### Quantitative
- **AOV Increase**: Target +15% through upselling
- **Insurance Uptake**: Target 30% of orders use insured shipping
- **Cart Conversion**: Monitor if direct checkout button improves conversion
- **Support Tickets**: Measure reduction in "package lost" complaints

### Qualitative
- User feedback on pricing transparency
- Admin feedback on system flexibility
- Reduced manual bundle management effort

---

**Status:** Planned
**Replaces:**
- `/TODO/2025-10-19_TODO_tiered-pricing.md`
- `/TODO/2025-10-19_TODO_upselling-options.md`