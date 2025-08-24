# Invoice-Stock-Management Technical Implementation Draft

## Epic Overview
Transform the existing wallet-based e-commerce system to an invoice-based order system with temporary stock reservation during payment windows. The implementation introduces one-time crypto address generation per order, replaces immediate wallet deductions with payment confirmations, and implements comprehensive order lifecycle management.

## Technical Approach

### Architectural Decisions
1. **New Order Model**: Create comprehensive Order model to replace direct Item purchases
2. **Stock Reservation System**: Implement temporary stock holds during payment windows
3. **One-Time Address Generation**: Extend existing CryptoAddressGenerator for unique order addresses
4. **Background Task Service**: Create order timeout monitoring and cleanup system
5. **Payment Observer Integration**: Extend existing notification system for payment confirmations
6. **Admin Order Management**: Add dedicated order management interface to admin handlers

### Database Schema Changes
The system will introduce new models while maintaining existing User dual ID architecture (internal `id` + `telegram_id`):

**New Models**:
- `Order`: Central order management
- `OrderItem`: Line items linking orders to purchased items
- `ReservedStock`: Temporary stock holds

**Modified Models**:
- `User`: Add timeout tracking fields
- Keep existing balance fields for migration compatibility

## Implementation Tasks

### Phase 1: Database Foundation (2-3 hours)

#### Task 1.1: Create Order Model
**File**: `models/order.py`
**Dependencies**: SQLAlchemy, existing base models
**Database Impact**: New `orders` table with foreign key to `users.id`

Create Order model with fields:
- `id` (Primary Key)
- `user_id` (Foreign Key to `users.id` - internal ID)
- `status` (Enum: created, paid, shipped, cancelled, expired)
- `total_amount` (Float)
- `currency` (String: BTC/ETH/LTC/SOL)
- `payment_address` (String, unique)
- `private_key` (String, encrypted)
- `expires_at` (DateTime)
- `created_at` (DateTime)
- `paid_at` (DateTime, nullable)
- `shipped_at` (DateTime, nullable)

Include OrderDTO and OrderStatus enum classes.

#### Task 1.2: Create OrderItem Model
**File**: `models/orderItem.py`
**Dependencies**: Order model, Item model
**Database Impact**: New `order_items` table with foreign keys to orders and items

Create OrderItem model linking orders to specific items:
- `id` (Primary Key)
- `order_id` (Foreign Key to `orders.id`)
- `item_id` (Foreign Key to `items.id`)
- `price_at_purchase` (Float - snapshot of item price)
- `created_at` (DateTime)

Include OrderItemDTO class.

#### Task 1.3: Create ReservedStock Model
**File**: `models/reservedStock.py`
**Dependencies**: Order model, Item model
**Database Impact**: New `reserved_stock` table

Create ReservedStock model for temporary stock holds:
- `id` (Primary Key)
- `order_id` (Foreign Key to `orders.id`)
- `category_id` (Foreign Key to `categories.id`)
- `subcategory_id` (Foreign Key to `subcategories.id`)
- `quantity` (Integer)
- `reserved_at` (DateTime)
- `expires_at` (DateTime)

Include ReservedStockDTO class.

#### Task 1.4: Update User Model
**File**: `models/user.py`
**Dependencies**: Existing User model
**Database Impact**: Add new columns to `users` table

Add timeout tracking fields:
- `timeout_count` (Integer, default=0)
- `last_timeout_at` (DateTime, nullable)

Update UserDTO class accordingly.

#### Task 1.5: Update Database Imports
**File**: `db.py`
**Dependencies**: New model imports
**Database Impact**: Include new models in table creation

Add imports for new models:
```python
from models.order import Order
from models.orderItem import OrderItem
from models.reservedStock import ReservedStock
```

### Phase 2: Repository Layer (2-3 hours)

#### Task 2.1: Create OrderRepository
**File**: `repositories/order.py`
**Dependencies**: Order model, database session management
**Integration Points**: Follows existing repository patterns from `repositories/user.py`

Implement repository methods:
- `create(order_dto: OrderDTO) -> int` - Returns order ID
- `get_by_id(order_id: int) -> OrderDTO`
- `get_by_user_id(user_id: int) -> OrderDTO | None` - Get active order
- `get_by_payment_address(address: str) -> OrderDTO`
- `update_status(order_id: int, status: OrderStatus)`
- `update_payment_confirmation(order_id: int, paid_at: datetime)`
- `get_expired_orders() -> list[OrderDTO]`
- `get_orders_ready_for_shipment() -> list[OrderDTO]`
- `update_shipped(order_id: int, shipped_at: datetime)`

#### Task 2.2: Create OrderItemRepository
**File**: `repositories/orderItem.py`
**Dependencies**: OrderItem model, database session management

Implement repository methods:
- `create_many(order_items: list[OrderItemDTO]) -> None`
- `get_by_order_id(order_id: int) -> list[OrderItemDTO]`
- `delete_by_order_id(order_id: int) -> None`

#### Task 2.3: Create ReservedStockRepository
**File**: `repositories/reservedStock.py`
**Dependencies**: ReservedStock model, database session management

Implement repository methods:
- `create_reservations(reservations: list[ReservedStockDTO]) -> None`
- `get_by_order_id(order_id: int) -> list[ReservedStockDTO]`
- `release_by_order_id(order_id: int) -> None`
- `get_expired_reservations() -> list[ReservedStockDTO]`
- `check_availability(category_id: int, subcategory_id: int, quantity: int) -> bool`

#### Task 2.4: Update ItemRepository for Stock Reservations
**File**: `repositories/item.py`
**Dependencies**: Existing ItemRepository, ReservedStock model
**Integration Points**: Modify existing stock checking methods

Add methods:
- `get_available_qty_with_reservations(item_dto: ItemDTO) -> int`
- `reserve_items_for_order(category_id: int, subcategory_id: int, quantity: int, order_id: int) -> list[ItemDTO]`
- `mark_items_as_sold_from_order(order_id: int) -> None`

#### Task 2.5: Update UserRepository for Timeout Tracking
**File**: `repositories/user.py`
**Dependencies**: Existing UserRepository
**Integration Points**: Add timeout-related methods

Add methods:
- `increment_timeout_count(user_id: int) -> None`
- `get_users_by_timeout_count(min_count: int) -> list[UserDTO]`

### Phase 3: Service Layer (3-4 hours)

#### Task 3.1: Create OrderService
**File**: `services/order.py`
**Dependencies**: OrderRepository, CryptoAddressGenerator, NotificationService
**Integration Points**: Cart system, payment processing, admin notifications

Implement core order management:
- `create_order_from_cart(user_id: int, currency: str) -> OrderDTO`
- `reserve_stock_for_cart(user_id: int, cart_items: list[CartItemDTO]) -> dict`
- `cancel_order(order_id: int, user_initiated: bool) -> None`
- `confirm_payment(order_id: int) -> None`
- `expire_order(order_id: int) -> None`
- `ship_order(order_id: int) -> None`
- `get_order_details_for_user(user_id: int) -> dict`

**Key Implementation Details**:
- Generate unique crypto address per order using existing CryptoAddressGenerator
- Validate stock availability before order creation
- Handle partial stock scenarios (reduce quantities vs reject)
- Integrate with admin notification system
- Support 30-60 minute configurable timeout

#### Task 3.2: Create BackgroundTaskService
**File**: `services/background_tasks.py`
**Dependencies**: OrderRepository, ReservedStockRepository, NotificationService
**Security Measures**: Admin-only access, proper error handling

Implement background processing:
- `process_expired_orders() -> None`
- `cleanup_expired_reservations() -> None`
- `monitor_order_timeouts() -> None`
- `schedule_cleanup_tasks() -> None`

**Technical Constraints**:
- Use asyncio for background task scheduling
- Integrate with existing error handling patterns
- Log all cleanup operations for admin visibility

#### Task 3.3: Extend NotificationService for Orders
**File**: `services/notification.py`
**Dependencies**: Existing NotificationService, Order models
**Integration Points**: Admin notification system, localization

Add order notification methods:
- `order_created(order: OrderDTO, user: UserDTO) -> None`
- `payment_received(order: OrderDTO, user: UserDTO, private_key: str) -> None`
- `order_expired(order: OrderDTO, user: UserDTO) -> None`
- `order_cancelled(order: OrderDTO, user: UserDTO, admin_initiated: bool) -> None`
- `order_shipped(order: OrderDTO, user: UserDTO) -> None`

#### Task 3.4: Update CartService for Order Integration
**File**: `services/cart.py`
**Dependencies**: Existing CartService, OrderService
**Integration Points**: Checkout process, payment flow

Modifications to existing methods:
- Update `buy_processing()` to create orders instead of immediate purchases
- Add currency selection flow before order creation
- Remove wallet balance checks, add stock availability checks
- Integrate order creation with existing cart clearing logic

### Phase 4: Handler Updates (2-3 hours)

#### Task 4.1: Update User Cart Handlers
**File**: `handlers/user/cart.py`
**Dependencies**: Updated CartService, OrderService
**Integration Points**: Telegram callback handling, user interface

Modify existing cart handlers:
- Update checkout flow to show currency selection
- Add order status checking before allowing new orders
- Implement order cancellation handler
- Add order status display handler

#### Task 4.2: Create Admin Order Management Handlers
**File**: `handlers/admin/order_management.py`
**Dependencies**: OrderService, admin authentication
**Integration Points**: Admin menu system, notification callbacks

Implement admin order interface:
- `show_orders_ready_for_shipment()`
- `mark_order_as_shipped(order_id: int)`
- `view_order_details(order_id: int)`
- `search_users_by_timeout_count()`
- `manually_expire_order(order_id: int)`

#### Task 4.3: Update Admin Menu
**File**: `handlers/admin/admin.py`
**Dependencies**: Existing admin handlers
**Integration Points**: Admin navigation system

Add order management menu items:
- "📦 Order Management" button
- Link to order management handlers
- Update admin navigation callbacks

### Phase 5: Payment Processing Integration (2-3 hours)

#### Task 5.1: Extend CryptoAddressGenerator for One-Time Addresses
**File**: `utils/CryptoAddressGenerator.py`
**Dependencies**: Existing crypto utilities
**Security Measures**: Unique seed generation per order

Add methods for one-time address generation:
- `generate_one_time_address(currency: str, order_id: int) -> dict`
- `validate_address_uniqueness(address: str, currency: str) -> bool`

**Technical Requirements**:
- Generate unique seed per order for address uniqueness
- Support BTC, ETH, LTC, SOL currencies
- Return both address and private key
- Ensure address is double-checked for validity

#### Task 5.2: Create Payment Observer Service
**File**: `services/payment_observer.py`
**Dependencies**: OrderService, existing crypto APIs
**Integration Points**: Background task system, webhook processing

Implement payment monitoring:
- `monitor_order_payments() -> None`
- `process_payment_confirmation(address: str, amount: float, currency: str) -> None`
- `validate_payment_amount(order_id: int, received_amount: float) -> bool`

#### Task 5.3: Create Payment Processing Endpoints
**File**: `processing/order_payment.py`
**Dependencies**: Payment observer, webhook authentication
**Security Measures**: Signature verification, request validation

Implement webhook endpoints:
- `POST /cryptoprocessing/order_payment` - Payment confirmation webhook
- Request signature verification using existing patterns
- Integration with OrderService for payment confirmation

### Phase 6: Localization & UI (1-2 hours)

#### Task 6.1: Add Order-Related Localization
**Files**: `l10n/en.json`, `l10n/de.json`
**Dependencies**: Existing localization system

Add localization keys for:
- Order creation messages
- Payment instructions with countdown
- Order status updates
- Timeout notifications
- Currency selection prompts
- Admin order management interface

**Key Messages**:
- `order_created_instructions`
- `payment_timeout_warning`
- `order_expired_message`
- `currency_selection_prompt`
- `admin_order_ready_for_shipment`
- `admin_order_shipped_confirmation`

#### Task 6.2: Update Message Formatting
**File**: `services/message.py`
**Dependencies**: Existing MessageService, Order models
**Integration Points**: Localization system

Add order message formatting:
- `create_order_payment_instructions(order: OrderDTO) -> str`
- `create_order_status_message(order: OrderDTO) -> str`
- `create_admin_order_summary(order: OrderDTO, user: UserDTO) -> str`

### Phase 7: Background Task Scheduler (1-2 hours)

#### Task 7.1: Integrate Background Tasks with Bot Lifecycle
**File**: `bot.py`
**Dependencies**: BackgroundTaskService
**Integration Points**: FastAPI lifecycle, existing bot initialization

Add background task initialization:
- Start background task scheduler on bot startup
- Integrate cleanup tasks with existing error handling
- Ensure proper shutdown procedures

#### Task 7.2: Create Background Task Configuration
**File**: `config.py`
**Dependencies**: Existing configuration system

Add configuration options:
- `ORDER_TIMEOUT_MINUTES` (default: 30)
- `BACKGROUND_TASK_INTERVAL_SECONDS` (default: 60)
- `MAX_USER_TIMEOUTS` (default: 3)

### Phase 8: Migration & Cleanup (1-2 hours)

#### Task 8.1: Data Migration Strategy
**File**: `migrations/wallet_to_order_migration.py`
**Dependencies**: Existing models, repository patterns
**Database Impact**: Handle existing wallet balances

Create migration script to:
- Preserve existing user wallet balances (no immediate removal)
- Add new fields to User model with defaults
- Create new tables with proper indexes
- Validate data integrity post-migration

#### Task 8.2: Backward Compatibility Measures
**Files**: Various handlers and services
**Dependencies**: Existing user interface

Implement compatibility:
- Keep existing wallet balance display in user profiles
- Add deprecation notices for wallet-based features
- Provide clear migration path messaging

## Risk Assessment & Mitigation

### High Risk: Race Conditions in Stock Reservation
**Mitigation**: 
- Implement database-level unique constraints
- Use SELECT FOR UPDATE in critical stock checking queries
- Add retry logic for concurrent order creation

### High Risk: Payment Monitoring Reliability
**Mitigation**:
- Implement redundant payment checking mechanisms
- Add manual payment confirmation option for admins
- Create payment reconciliation reports

### Medium Risk: Background Task Reliability
**Mitigation**:
- Use database-based task tracking
- Implement task failure recovery mechanisms
- Add comprehensive logging for debugging

### Medium Risk: User Experience During Transition
**Mitigation**:
- Gradual feature rollout with feature flags
- Clear user messaging about system changes
- Maintain existing functionality during transition period

## Testing Strategy

### Unit Testing Priorities:
1. OrderService stock reservation logic
2. CryptoAddressGenerator uniqueness validation
3. BackgroundTaskService timeout processing
4. Payment amount validation logic

### Integration Testing:
1. Complete order lifecycle (creation → payment → shipment)
2. Stock reservation and release mechanisms
3. Admin notification delivery
4. Background task execution

### Manual Testing Scenarios:
1. Multiple users attempting to purchase same items simultaneously
2. Order timeout scenarios with proper stock release
3. Payment confirmation edge cases
4. Admin order management workflow

## Dependencies & Integration Points

### External Dependencies:
- Existing CryptoApiManager for payment processing
- Telegram Bot API for notifications
- SQLAlchemy for database operations
- FastAPI for webhook endpoints

### Internal Integration Points:
- Repository pattern consistency across new models
- Service layer architecture alignment
- Handler organization following existing patterns
- Localization system integration
- Admin authentication and authorization

## Success Criteria Validation

### Technical Metrics:
- Zero stock overselling incidents (verified by database constraints)
- Payment detection within 15 minutes (monitored by background tasks)
- Order timeout accuracy within 1 minute (validated by background service logs)
- Admin notification delivery 100% success rate (tracked by notification service)

### User Experience Metrics:
- Clear order status communication throughout lifecycle
- Intuitive currency selection process
- Seamless admin order management workflow
- Proper handling of edge cases (insufficient stock, payment delays)

---

**Implementation Order**: Execute phases sequentially to maintain system stability
**Estimated Total Effort**: 12-18 hours across 8 phases
**Critical Path Dependencies**: Database models → Repositories → Services → Handlers
**Testing Integration**: Unit tests for each service method, integration tests for complete workflows

**Next Steps**: 
1. Begin with Phase 1 database foundation
2. Implement core repositories and services
3. Update user-facing handlers
4. Integrate payment processing
5. Add comprehensive testing and monitoring