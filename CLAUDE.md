# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development
- **Start bot locally**: `python run.py`
- **Install dependencies**: `pip install -r requirements.txt`
- **Install SQLCipher support**: `pip install sqlcipher3` (Linux only)

### Docker Development
- **Start with Docker**: `docker-compose up`
- **Build container**: `docker build .`

### Environment Setup
- Copy environment variables from README section 1.0 to `.env` file
- For development: Set `RUNTIME_ENVIRONMENT="dev"`; NEVER USER NGROK!!!
- For production: Set `RUNTIME_ENVIRONMENT="prod"` and configure domain in docker-compose.yml

## Architecture Overview

### Core Components

**Entry Points:**
- `run.py` - Main application entry point, handles multibot vs single bot mode
- `bot.py` - FastAPI app with webhook handling, bot initialization, and error handling
- `config.py` - Environment variable configuration and runtime setup

**Database Layer:**
- `db.py` - SQLAlchemy setup with support for both SQLite and SQLCipher encryption
- `models/` - SQLAlchemy ORM models (User, Item, Cart, Buy, Category, etc.)
- `repositories/` - Database access layer with async/sync session handling

**Business Logic:**
- `services/` - Business logic layer (UserService, PaymentService, NotificationService, etc.)
- `handlers/` - Telegram bot message/callback handlers split by user type:
  - `handlers/user/` - User-facing functionality (profiles, categories, cart)
  - `handlers/admin/` - Admin functionality (inventory, user management, analytics)
  - `handlers/common/` - Shared handlers

**Payment System:**
- `models/order.py` - Order model for one-time crypto address payments
- `services/order.py` - Order creation, stock reservation, and lifecycle management
- `services/background_tasks.py` - Background service for order expiration handling
- `processing/processing.py` - Webhook endpoints for payment confirmation
- `utils/CryptoAddressGenerator.py` - One-time crypto address generation per order

**Infrastructure:**
- `middleware/` - Database session and throttling middleware
- `utils/` - Localization, filters, and utility functions
- `l10n/` - Internationalization files (English/German)

### Key Architectural Patterns

**Dual Database Support:**
- Async SQLAlchemy for standard SQLite
- Sync SQLAlchemy for SQLCipher encrypted databases
- Session abstraction in `db.py` handles both modes transparently

**Multibot Architecture:**
- Single process can manage multiple bot instances
- Main bot acts as manager, creates sub-bots via `/add $TOKEN` command
- Experimental feature controlled by `MULTIBOT` environment variable

**Security Features:**
- Webhook signature verification for Telegram and KryptoExpress
- Database encryption via SQLCipher
- Admin access control via `ADMIN_ID_LIST`
- Request throttling middleware

**Payment System (New One-Time Address Model):**
- One-time crypto addresses generated per order (no wallet system)
- 60-minute payment window with automatic order expiration
- Stock reservation during payment period
- Background task service handles order cleanup
- Admin notifications for new orders with private keys
- Order management interface for shipment tracking
- Supports BTC, ETH, LTC, SOL currencies

### Development Guidelines

**Git Workflow (IMPORTANT):**
- **ALWAYS** create feature branches for significant changes: `git checkout -b feature/feature-name`
- Make incremental commits as you complete each component
- **NEVER** add references to Claude, AI, or code generation tools in commit messages
- Use clean, professional commit messages describing the actual changes made
- **MANDATORY**: Use the git-gatekeeper agent for code review before merging any significant changes
- Examples of when to use git-gatekeeper:
  - New features or major functionality changes
  - Database model changes
  - Security-related modifications
  - API endpoint changes
  - Payment system modifications
- Create pull requests for team review
- Never commit major changes directly to develop/main without review

**Database Operations:**
- Use repository pattern for data access
- Handle both AsyncSession and Session types in service methods
- Database migrations happen automatically via `create_db_and_tables()`

**Error Handling:**
- Global exception handlers send errors to admin notifications
- Critical errors include stack traces sent as files if too long

**Localization:**
- Add new languages by creating JSON files in `l10n/` directory
- Use `Localizator.get_text(BotEntity, key)` for all user-facing text

**Mandatory Development Workflow:**
1. **For feature requests:**
   - Requirements agent first clarifies and documents complete requirements
   - Requirements agent creates structured todo list for development
   - requirements agent asks back for clarification and also consults the gatekeeper agent if the requirements have been elicitated correctly
   - Then follow standard development workflow

2. **After implementing any significant feature, ALWAYS follow this sequence:**
   - First call git-gatekeeper agent for code review
   - Then call test-coverage-guardian agent for test coverage analysis
   - If critical issues found: requirements agent defines fix requirements
   - Only proceed with commits after both agents approve

3. **Requirements Agent Role:** Requirements analysis and specification
   - Clarifies ambiguous requirements and defines complete specifications
   - Creates structured todo lists for development agents
   - Defines security fix requirements when issues are identified
   - Does NOT write code - only defines what needs to be implemented
   - for every new feature, the requirements agent creates a folder in the project root called "todos"
   - all todos will be written into files in this directory

4. **Telegram-Bot-Architect Role:** Technical design and architecture
   - Transforms high-level requirements into detailed technical implementation tasks
   - Bridges gap between business requirements and technical implementation
   - Creates comprehensive technical drafts with granular, trackable development tasks
   - Receives requirements from requirements agent and prepares technical tasks for development agent
   - Does NOT implement code - only creates technical specifications and task breakdowns
   - Does NOT define or create tests - testing is solely the responsibility of test-coverage-guardian agent
   - can give hints for the testing agent on what to look
   - documents it in files as well in the todos-folder

5. **Git-Gatekeeper Role:** Code review and quality assessment only
   - Identifies security issues, code quality problems, architectural concerns
   - Returns specific actionable todos for requirements agent to define
   - Does NOT fix code directly - delegates to requirements → development flow

6. **Test-Coverage-Guardian Role:** Testing analysis and test writing only
   - Analyzes test coverage gaps and proposes comprehensive test strategies
   - Writes missing tests and identifies testing requirements
   - Returns specific test todos for the telegram-bot-feature-developer

7. **Telegram-Bot-Feature-Developer Role:** Implementation and fixes
   - Implements new features using complete development workflow
   - Receives structured technical tasks from telegram-bot-architect agent
   - Implements fixes based on requirements agent specifications
   - Must re-call review agents after making fixes

8. **Security Fix Workflow:**
   - git-gatekeeper identifies security issues → requirements agent defines fix requirements → telegram-bot-architect creates technical fix plan → development agent implements → re-review cycle

**Example Workflows:**
```
User: "Add weather command to bot"
→ requirements agent clarifies requirements and creates todo
→ telegram-bot-architect creates technical implementation plan
→ telegram-bot-feature-developer implements feature
→ git-gatekeeper reviews → test-coverage-guardian tests → approve/fix cycle

Security Issue Found:
→ git-gatekeeper identifies security vulnerability
→ requirements agent defines security fix requirements
→ telegram-bot-architect creates technical fix plan
→ telegram-bot-feature-developer implements fixes
→ git-gatekeeper re-reviews → approve when secure
```

**Testing:**
- No test framework currently configured
- Use live bot testing via demo bot mentioned in README but you must never run ngrok
- Manual testing encouraged for new features

## Environment Variables

All required environment variables are documented in README section 1.0. Key variables:
- `TOKEN` - Telegram bot token
- `ADMIN_ID_LIST` - Comma-separated admin Telegram IDs
- `DB_ENCRYPTION` - Enable SQLCipher database encryption
- `RUNTIME_ENVIRONMENT` - "dev" (ngrok) or "prod" (domain-based)
- `MULTIBOT` - Enable experimental multibot functionality
- Cryptocurrency API keys for payment processing

## Payment Workflow (One-Time Address System)

The bot now uses a one-time crypto address payment system instead of wallet balances:

### User Payment Flow:
1. User adds items to cart
2. User selects "Checkout" 
3. User chooses payment currency (BTC/ETH/LTC/SOL)
4. System generates unique one-time crypto address
5. User receives payment address and 60-minute timer
6. Requested amount from Stock in the user's cart is reserved for 60 minutes
7. User sends payment to provided address within given time frame
8. System monitors for payment confirmation
9. Admin receives notification with order details and private key for him to control the crypto asset
10. Admin ships order and marks as shipped via admin interface
11. User receives shipment confirmation

### Order Expiration:
- Orders expire after 60 minutes if no payment received
- Reserved stock is released back to inventory
- User timeout count is incremented
- User receives expiration notification
- Background service handles automatic cleanup

### Admin Order Management:
- Access via Admin Menu → "📦 Order Management"
- View orders ready for shipment (payment received)
- Mark orders as shipped with confirmation
- Search users by timeout count
- Each new order notification includes private key for admin

### Technical Implementation:
- `OrderService.create_order_from_cart()` - Creates order with one-time address
- `BackgroundTaskService` - Handles 60-minute expiration cleanup  
- `POST /cryptoprocessing/order_payment` - Payment webhook endpoint
- Order model tracks: user_id, amount, currency, addresses, status, expiration
- Stock reservation via `OrderService.reserve_stock_for_cart()`
# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.