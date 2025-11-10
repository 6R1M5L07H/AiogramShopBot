# TODO: README Update - Recent Features

## Goal
Integrate recently implemented features (last few weeks) into README.md at appropriate locations.

**IMPORTANT**: Do NOT add features as a large "Key Features" list at the beginning (felt inappropriate). Instead, integrate organically into existing sections.

## Implemented Features (Recent Weeks)

### 1. Tiered Pricing System
- Quantity-based bulk discounts with greedy algorithm (largest tier first)
- Display in Cart, Order Payment Screen, Order History (User + Admin)
- JSON import with `price_tiers` array support
- Generator script support for templates
- Backward compatible with legacy flat pricing

**Possible README Integration**:
- Extend Section 3.3.1 (Add Items) with Tier Pricing example
- Add new subsection "3.3.1.3 Tiered Pricing"

### 2. Unified Order Management System
- Unified system for Admin and User contexts
- Filters: ALL, ACTIVE, REQUIRES_ACTION, COMPLETED, CANCELLED
- Order Detail View with tier breakdown display
- Mark as Shipped, Cancel Order with custom reason
- Shipping Address Encryption Notice for users

**Possible README Integration**:
- Extend Section 2.4 (Purchase History) with screenshots and filter options
- Add new Section "3.7 Order Management" (between User Management and Analytics)

### 3. Strike System & User Banning
- Automatic banning after configurable strikes
- Strike reasons: Late Cancellation, Payment Timeout
- Admin exemption (configurable)
- Unban via Wallet Top-Up (threshold configurable)

**Possible README Integration**:
- Extend Section 3.4 (User Management) with "3.4.3 Strike System & Bans"

### 4. Data Retention & GDPR Compliance
- Automatic deletion: Shipping Addresses (30 days), Referral Data (365 days)
- Daily cleanup job
- Encrypted Shipping Address Storage (AES-256)

**Possible README Integration**:
- New section "Security & Privacy" after Admin Manual
- Or extend Environment Variables Section 1.0

### 5. Performance Optimizations
- N+1 Query Prevention with selectinload()
- Atomic Stock Reservation (SELECT FOR UPDATE)
- Race Condition Safety

**Possible README Integration**:
- Technical details might fit better in project documentation?
- Or brief "Technical Architecture" section at the end

## Open Tasks

- [ ] Analyze existing README structure
- [ ] Identify sensible integration points for each feature
- [ ] Create screenshots/GIFs for new features (like existing sections)
- [ ] Extend existing sections instead of large new list at beginning
- [ ] Add Tier Pricing example to JSON example in Section 3.3.1.1
- [ ] Maintain consistent style with existing sections

## Notes

- User found placement at beginning as "Key Features" inappropriate
- Better: Integrate organically into existing sections
- README already has good flow (User Manual → Admin Manual → Technical)
- New features should fit into this existing flow