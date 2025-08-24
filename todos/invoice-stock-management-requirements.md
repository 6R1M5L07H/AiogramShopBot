# Invoice-Stock-Management Feature Requirements

## Epic Overview
Transform the Telegram bot e-commerce system from a wallet-based payment system to an invoice-based system with temporary stock reservation during payment windows. This is a clean implementation without legacy wallet balance migration concerns.

## Current System Analysis
- **Existing Flow**: User wallets → balance checks → immediate purchase
- **Current Models**: User (with balances), Item, Cart, CartItem, Buy, Deposit
- **Payment System**: Shared crypto addresses with deposit tracking
- **Stock Management**: Items marked `is_sold=True` on purchase

## Core Requirements

### 1. Purchase Flow Transformation
**User Story**: As a customer, I want to create orders with one-time payment addresses so I can pay directly without maintaining wallet balances.

**Acceptance Criteria**:
- User selects items → adds to cart → presses "purchase" → selects currency
- System generates unique and double checked valid one-time crypto address for selected currency so that no currency is lost
- Payment instructions shown in single message with countdown timer
- Support for BTC/ETH/LTC/SOL (using existing crypto configuration)

### 2. Stock Reservation System
**User Story**: As a customer, I want items reserved during my payment window so they remain available while I complete payment.

**Acceptance Criteria**:
- Items reserved immediately when order is created (after currency selection)
- Configurable reservation timeout (30 minutes default)
- Cart items checked against stock availability before order creation
- Partial stock handling: reduce quantities if partially available, inform user
- No stock available: inform user, no order created
- Support multiple items per order with individual stock checks

### 3. Order Lifecycle Management
**User Story**: As a system, I need to manage order states to ensure proper inventory and payment tracking.

**Acceptance Criteria**:
- Order states: created → paid → shipped (or cancelled/expired)
- Only one active order per user allowed
- New orders blocked until current order is "shipped"
- Payment observer monitors for payment confirmation
- Admin exclusive access to private keys

### 4. Admin Notifications & Control
**User Story**: As an admin, I want complete visibility and control over the order process.

**Acceptance Criteria**:
- Admin notified when purchase process starts
- Admin notified when payment received (with order details + private key)
- Admin can refund unpaid orders
- Admin can mark orders as shipped
- Admin interface for order management

### 5. Timeout & Cancellation Handling
**User Story**: As a system, I need to handle order timeouts and cancellations to free up reserved stock.

**Acceptance Criteria**:
- Configurable timeout (30min default)
- On timeout: items return to stock, remove from cart, increment user timeout counter
- User "cancel" button: immediate cancellation, admin notification
- Track user timeout counter for abuse prevention
- Background service for automatic cleanup

## Technical Constraints & Integration Points

### Must Integrate With:
- Existing `CryptoApiManager` for payment processing
- Current crypto configuration (BTC/ETH/LTC/SOL)
- Existing admin notification system
- Current localization system (l10n/)
- Existing middleware and session handling

### Technical Constraints:
- Cart items NOT reserved (only reserved when order created)
- Must use existing payment observer system
- Dual database support (SQLite/SQLCipher)
- Maintain existing admin access control

## Clarification Required

### High Priority Questions:
1. **Currency & Pricing**: Order totals in USD equivalent or crypto amounts?
2. **Stock Partial Fulfillment**: Reduce quantities vs reject entire order?
3. **Payment Confirmation**: Required blockchain confirmations per currency?
4. **Admin Interface**: Dedicated panel vs extend existing admin handlers?
5. **Timeout Configuration**: Per-admin configurable vs system-wide?

### Architecture Questions:
1. **Payment Observer**: Extend existing vs create new monitoring system?
2. **Background Tasks**: New service vs extend existing background processing?
3. **Database Migration**: How to handle existing user wallet balances?
4. **Webhook Integration**: Real-time payment notifications needed?

## Risk Assessment

### High Risk:
- Race conditions in stock reservation
- Payment monitoring reliability across blockchains
- Database consistency during concurrent operations

### Medium Risk:
- Background task reliability for timeouts
- Migration complexity from wallet system
- User experience during transition

### Low Risk:
- Admin interface extensions
- Notification system integration
- Localization updates

## Dependencies
- Existing crypto address generation system
- Current payment monitoring infrastructure
- Admin notification framework
- Database session management
- Cart and item repository patterns

## Success Criteria
- Zero stock overselling incidents
- Payment detection within 15 minutes of confirmation
- Order timeout accuracy within 1 minute
- Admin notification delivery 100% success rate
- Seamless user experience with clear status updates

---
**Status**: Requirements Analysis Complete - Awaiting Clarification
**Next Step**: Technical Architecture Design after requirements approval