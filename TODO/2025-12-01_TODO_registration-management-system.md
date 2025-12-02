# TODO: 3-Tier Registration Management System with User List

**Created:** 2025-12-01
**Status:** 🟡 Ready for Implementation
**Priority:** High (Business Critical)
**Estimated Effort:** 90-120 minutes

---

## Überblick

Implementierung eines Registration-Mode-Systems mit 3 Stufen + erweiterte User-Management-Features:

- **"open"**: Normale Registrierung, User können sofort Shop nutzen (status="approved")
- **"request_approval"**: User werden erstellt mit status="pending", erhalten Nachricht mit Support-Link
- **"closed"**: User werden erstellt mit status="closed_registration" (Warteliste!), Benachrichtigung über Wartelistenstatus

**Neue User Management Features:**
- User List mit Filtern (Warteliste, Banned, später: Alle)
- User Detail View mit Statistiken (Registrierung, Status, Umsatz, Käufe, Kontaktbutton)
- Batch-Operations (gesamte Warteliste freischalten mit Notification-Auswahl)

**Key Benefits:**
- Admin-kontrollierte Registrierung für exklusive/invite-only Shops
- Warteliste als Marketing-Tool (Künstliche Knappheit)
- Spam-Prävention durch Approval-Workflow

---

## Änderungen

### 1. Database Schema

#### Neue Tabelle: `models/system_settings.py`
```python
from sqlalchemy import Column, String, DateTime, func
from models.base import Base

class SystemSettings(Base):
    """
    Key-value store for runtime-configurable bot settings.
    Allows changing settings without bot restart.
    """
    __tablename__ = 'system_settings'

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

#### User Model erweitern: `models/user.py`
```python
from enums.approval_status import ApprovalStatus

# Neue Felder hinzufügen:

# === Approval System ===
approval_status = Column(String, default=ApprovalStatus.APPROVED.value)
# Possible values: "approved", "pending", "closed_registration", "rejected"
# Uses ApprovalStatus enum for type safety

approval_requested_at = Column(DateTime, nullable=True)
# Timestamp when user requested registration (pending/closed modes)

approved_at = Column(DateTime, nullable=True)
# Timestamp when user was approved
# For "open" mode: equals registered_at

approved_by_admin_id = Column(Integer, nullable=True)
# Telegram ID of admin who approved (NULL for auto-approved in "open" mode)

rejection_reason = Column(String, nullable=True)
# Human-readable reason for rejection (shown to user)

# === User Statistics (TODO: Separate Trust-Level System) ===
# Reference: See TODO/2025-12-01_TODO_user-trust-level-system.md
# These fields are placeholders for future trust-level feature
# Currently set to DUMMY values (0, NULL)

lifetime_revenue = Column(Float, default=0.0)
# TODO: Aggregate from completed orders
# DUMMY: Always 0.0 for now

lifetime_orders = Column(Integer, default=0)
# TODO: Count completed orders
# DUMMY: Always 0 for now

first_order_date = Column(DateTime, nullable=True)
# TODO: Set on first completed order
# DUMMY: Always NULL for now

last_order_date = Column(DateTime, nullable=True)
# TODO: Update on each completed order
# DUMMY: Always NULL for now
```

#### Neue Enum: `enums/approval_status.py`
```python
from enum import Enum

class ApprovalStatus(str, Enum):
    """
    User approval status for registration management.

    APPROVED: User can access shop (normal users)
    PENDING: Waiting for admin approval (request_approval mode)
    CLOSED_REGISTRATION: On waitlist (closed mode)
    REJECTED: Registration denied by admin
    """
    APPROVED = "approved"
    PENDING = "pending"
    CLOSED_REGISTRATION = "closed_registration"
    REJECTED = "rejected"
```

---

### 2. Configuration

**Keine neuen .env Variablen!**

Verwende existierende:
- `PAGE_ENTRIES=8` - Für User List Pagination
- `BOT_LANGUAGE=de` - Für Language Fallback
- `SUPPORT_LINK=@shop_support` - **REQUIRED** wenn registration_mode != "open"

**Validation:**
```python
# In config_validator.py
if SystemSettings.get("registration_mode") in ["request_approval", "closed"]:
    if not config.SUPPORT_LINK:
        raise ConfigurationError(
            "SUPPORT_LINK must be set in .env when registration mode is 'request_approval' or 'closed'"
        )
```

---

### 3. Repositories

#### Neu: `repositories/system_settings.py`
```python
class SystemSettingsRepository:
    @staticmethod
    async def get(key: str, default: str = None, session) -> str | None:
        """Get setting value, return default if not found"""
        stmt = select(SystemSettings).where(SystemSettings.key == key)
        result = await session_execute(stmt, session)
        setting = result.scalar_one_or_none()
        return setting.value if setting else default

    @staticmethod
    async def set(key: str, value: str, session) -> None:
        """Set or update setting value"""
        stmt = select(SystemSettings).where(SystemSettings.key == key)
        result = await session_execute(stmt, session)
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = SystemSettings(key=key, value=value)
            session.add(setting)

        await session_flush(session)

    @staticmethod
    async def get_registration_mode(session) -> str:
        """Returns 'open', 'request_approval', or 'closed'. Default: 'open'"""
        return await SystemSettingsRepository.get("registration_mode", "open", session)
```

#### Update: `repositories/user.py`
```python
from enums.approval_status import ApprovalStatus

# Neue Methoden:

@staticmethod
async def get_users_by_status(
    status: ApprovalStatus,
    page: int,
    session
) -> tuple[list[User], int]:
    """
    Get users by approval status with pagination.
    Uses config.PAGE_ENTRIES for page size.

    Returns:
        (users_list, total_count)
    """
    import config
    page_size = config.PAGE_ENTRIES
    offset = page * page_size

    # Count query
    count_stmt = select(func.count()).select_from(User).where(
        User.approval_status == status.value
    )
    result = await session_execute(count_stmt, session)
    total = result.scalar()

    # Data query
    stmt = select(User).where(
        User.approval_status == status.value
    ).order_by(
        User.approval_requested_at.asc()  # Oldest first (FIFO)
    ).offset(offset).limit(page_size)

    result = await session_execute(stmt, session)
    users = result.scalars().all()

    return users, total

@staticmethod
async def get_banned_users(
    page: int,
    session
) -> tuple[list[User], int]:
    """Get banned users (is_blocked=True) with pagination"""
    import config
    page_size = config.PAGE_ENTRIES
    offset = page * page_size

    count_stmt = select(func.count()).select_from(User).where(
        User.is_blocked == True
    )
    result = await session_execute(count_stmt, session)
    total = result.scalar()

    stmt = select(User).where(
        User.is_blocked == True
    ).order_by(
        User.blocked_at.desc()  # Most recent first
    ).offset(offset).limit(page_size)

    result = await session_execute(stmt, session)
    users = result.scalars().all()

    return users, total

@staticmethod
async def count_by_status(status: ApprovalStatus, session) -> int:
    """Count users by approval status"""
    stmt = select(func.count()).select_from(User).where(
        User.approval_status == status.value
    )
    result = await session_execute(stmt, session)
    return result.scalar() or 0

@staticmethod
async def approve_user(user_id: int, admin_id: int, session) -> User:
    """
    Approve user registration.
    Sets: approval_status='approved', approved_at=now(), approved_by_admin_id=admin_id
    """
    stmt = select(User).where(User.id == user_id)
    result = await session_execute(stmt, session)
    user = result.scalar_one()

    user.approval_status = ApprovalStatus.APPROVED.value
    user.approved_at = datetime.now(timezone.utc)
    user.approved_by_admin_id = admin_id

    await session_flush(session)
    return user

@staticmethod
async def reject_user(user_id: int, admin_id: int, reason: str, session) -> User:
    """Reject user registration with reason"""
    stmt = select(User).where(User.id == user_id)
    result = await session_execute(stmt, session)
    user = result.scalar_one()

    user.approval_status = ApprovalStatus.REJECTED.value
    user.rejection_reason = reason

    await session_flush(session)
    return user

@staticmethod
async def get_all_by_status(status: ApprovalStatus, session) -> list[User]:
    """Get ALL users by status (no pagination) - for batch operations"""
    stmt = select(User).where(
        User.approval_status == status.value
    ).order_by(User.approval_requested_at.asc())

    result = await session_execute(stmt, session)
    return result.scalars().all()

@staticmethod
async def approve_batch(user_ids: list[int], admin_id: int, session) -> int:
    """
    Approve multiple users at once.
    Returns count of approved users.
    """
    stmt = update(User).where(
        User.id.in_(user_ids)
    ).values(
        approval_status=ApprovalStatus.APPROVED.value,
        approved_at=datetime.now(timezone.utc),
        approved_by_admin_id=admin_id
    )

    result = await session_execute(stmt, session)
    await session_flush(session)
    return result.rowcount
```

---

### 4. Services

#### Update: `services/user.py`
```python
from enums.approval_status import ApprovalStatus

@staticmethod
async def create_if_not_exist(
    user_dto: UserDTO,
    session: AsyncSession | Session
) -> tuple[User | None, ApprovalStatus | None]:
    """
    Create user if not exists, respecting registration mode.

    Returns:
        (user, status_for_message)
        status_for_message: None if approved (normal flow), else ApprovalStatus enum value
    """
    user = await UserRepository.get_by_tgid(user_dto.telegram_id, session)

    if user:
        # Existing user - check status
        if user.approval_status == ApprovalStatus.REJECTED.value:
            return user, ApprovalStatus.REJECTED
        elif user.approval_status in [ApprovalStatus.PENDING.value, ApprovalStatus.CLOSED_REGISTRATION.value]:
            return user, ApprovalStatus(user.approval_status)
        else:
            # Approved user - update username if changed
            if user.telegram_username != user_dto.telegram_username:
                update_dto = UserDTO(**user.__dict__)
                update_dto.telegram_username = user_dto.telegram_username
                update_dto.can_receive_messages = True
                await UserRepository.update(update_dto, session)
                await session_commit(session)
            return user, None  # Normal flow

    # NEW USER - check registration mode
    reg_mode = await SystemSettingsRepository.get_registration_mode(session)

    match reg_mode:
        case "open":
            user_dto.approval_status = ApprovalStatus.APPROVED.value
            user_dto.approved_at = datetime.now(timezone.utc)
            # approved_by_admin_id = NULL (auto-approved)
            user_id = await UserRepository.create(user_dto, session)
            await CartRepository.get_or_create(user_id, session)
            await session_commit(session)

            # Notify admins if configured
            if config.NOTIFY_ADMINS_NEW_USER:
                await NotificationService.notify_new_user_registration(user_dto)

            return user, None  # Normal flow

        case "request_approval":
            user_dto.approval_status = ApprovalStatus.PENDING.value
            user_dto.approval_requested_at = datetime.now(timezone.utc)
            user_id = await UserRepository.create(user_dto, session)
            await session_commit(session)

            # Notify admins about pending approval
            await NotificationService.notify_pending_approval(user_dto)

            return user, ApprovalStatus.PENDING

        case "closed":
            user_dto.approval_status = ApprovalStatus.CLOSED_REGISTRATION.value
            user_dto.approval_requested_at = datetime.now(timezone.utc)
            user_id = await UserRepository.create(user_dto, session)
            await session_commit(session)

            return user, ApprovalStatus.CLOSED_REGISTRATION

        case _:
            # Fallback to open mode if invalid config
            user_dto.approval_status = ApprovalStatus.APPROVED.value
            user_dto.approved_at = datetime.now(timezone.utc)
            user_id = await UserRepository.create(user_dto, session)
            await CartRepository.get_or_create(user_id, session)
            await session_commit(session)
            return user, None
```

#### Update: `services/admin.py`
```python
from enums.approval_status import ApprovalStatus

# Erweitere existierendes User Management Menu

@staticmethod
async def get_user_management_menu() -> tuple[str, InlineKeyboardBuilder]:
    """
    User Management Main Menu.
    Add "User List" button to existing menu.
    """
    kb_builder = InlineKeyboardBuilder()

    # ... (existing buttons: Balance Management, Refund, etc.) ...

    # NEW: User List button
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "user_list"),
        callback_data=UserManagementCallback.create(
            level=5,  # NEW level for User List
            operation=UserManagementOperation.VIEW_USER_LIST
        )
    )

    kb_builder.adjust(1)
    kb_builder.row(AdminConstants.back_to_main_button)

    return Localizator.get_text(BotEntity.ADMIN, "user_management"), kb_builder

# NEW: Level 5 - User List Filters
@staticmethod
async def get_user_list_filters(session) -> tuple[str, InlineKeyboardBuilder]:
    """
    Show filter selection for user list.
    Displays counts per filter.
    """
    # Count users per filter
    waitlist_count = await UserRepository.count_by_status(ApprovalStatus.CLOSED_REGISTRATION, session)
    pending_count = await UserRepository.count_by_status(ApprovalStatus.PENDING, session)

    # Count banned users
    count_stmt = select(func.count()).select_from(User).where(User.is_blocked == True)
    result = await session_execute(count_stmt, session)
    banned_count = result.scalar() or 0

    kb_builder = InlineKeyboardBuilder()

    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "filter_waitlist").format(count=waitlist_count),
        callback_data=UserManagementCallback.create(
            level=6,
            operation=UserManagementOperation.VIEW_USER_LIST,
            filter="waitlist",
            page=0
        )
    )

    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "filter_pending").format(count=pending_count),
        callback_data=UserManagementCallback.create(
            level=6,
            operation=UserManagementOperation.VIEW_USER_LIST,
            filter="pending",
            page=0
        )
    )

    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "filter_banned").format(count=banned_count),
        callback_data=UserManagementCallback.create(
            level=6,
            operation=UserManagementOperation.VIEW_USER_LIST,
            filter="banned",
            page=0
        )
    )

    # TODO: Add "All Users" filter in future

    kb_builder.adjust(1)
    kb_builder.row(UserManagementCallback.create(level=0).get_back_button(0))

    return Localizator.get_text(BotEntity.ADMIN, "user_list_filters"), kb_builder

# NEW: Level 6 - Paginated User List
@staticmethod
async def get_filtered_user_list(
    callback: CallbackQuery,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Show paginated user list based on filter.
    Uses config.PAGE_ENTRIES for page size.
    """
    unpacked = UserManagementCallback.unpack(callback.data)
    filter_type = unpacked.filter  # "waitlist", "pending", "banned"
    page = unpacked.page or 0

    # Get users based on filter
    if filter_type == "waitlist":
        users, total = await UserRepository.get_users_by_status(
            ApprovalStatus.CLOSED_REGISTRATION, page, session
        )
    elif filter_type == "pending":
        users, total = await UserRepository.get_users_by_status(
            ApprovalStatus.PENDING, page, session
        )
    elif filter_type == "banned":
        users, total = await UserRepository.get_banned_users(page, session)
    else:
        users, total = [], 0

    kb_builder = InlineKeyboardBuilder()

    # User buttons
    for user in users:
        display_name = f"@{user.telegram_username}" if user.telegram_username else f"ID: {user.telegram_id}"
        kb_builder.button(
            text=display_name,
            callback_data=UserManagementCallback.create(
                level=7,
                operation=UserManagementOperation.VIEW_USER_DETAIL,
                user_id=user.id
            )
        )

    kb_builder.adjust(1)

    # Batch approve button (only for waitlist/pending)
    if filter_type in ["waitlist", "pending"] and total > 0:
        kb_builder.row(
            types.InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.ADMIN, "approve_all_batch"),
                callback_data=UserManagementCallback.create(
                    level=10,
                    operation=UserManagementOperation.APPROVE_BATCH_CONFIRM,
                    filter=filter_type
                ).pack()
            )
        )

    # Pagination using existing function
    import config
    max_page = (total - 1) // config.PAGE_ENTRIES if total > 0 else 0
    back_button = UserManagementCallback.create(level=5).get_back_button(5)
    await add_pagination_buttons(kb_builder, unpacked, lambda: max_page, back_button)

    # Message
    msg = Localizator.get_text(BotEntity.ADMIN, "user_list_header").format(
        filter=filter_type,
        page=page + 1,
        total_pages=max_page + 1,
        total_users=total
    )

    return msg, kb_builder

# NEW: Level 7 - User Detail View
@staticmethod
async def get_user_detail_view(
    callback: CallbackQuery,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Show detailed user information.
    Stats show DUMMY values (TODO: Trust-Level System).
    """
    unpacked = UserManagementCallback.unpack(callback.data)
    user_id = unpacked.user_id

    user = await UserRepository.get_by_id(user_id, session)

    # Format user data
    username_display = user.telegram_username or "N/A"
    registered = user.registered_at.strftime("%Y-%m-%d %H:%M") if user.registered_at else "N/A"
    status = user.approval_status

    # DUMMY Stats (TODO: Real implementation in Trust-Level System)
    total_revenue = "TODO (dummy: 0.00 €)"
    total_orders = "TODO (dummy: 0)"
    first_order = "TODO (dummy: N/A)"
    last_order = "TODO (dummy: N/A)"

    msg = Localizator.get_text(BotEntity.ADMIN, "user_detail").format(
        username=username_display,
        user_id=user.telegram_id,
        registered_at=registered,
        status=status,
        total_revenue=total_revenue,
        total_orders=total_orders,
        first_order=first_order,
        last_order=last_order
    )

    kb_builder = InlineKeyboardBuilder()

    # Contact button (always works with telegram_id)
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "contact_user"),
        url=f"tg://user?id={user.telegram_id}"
    )

    # Action buttons based on status
    if user.approval_status in [ApprovalStatus.PENDING.value, ApprovalStatus.CLOSED_REGISTRATION.value]:
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "approve_user"),
            callback_data=UserManagementCallback.create(
                level=8,
                operation=UserManagementOperation.APPROVE_USER,
                user_id=user.id
            )
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "reject_user"),
            callback_data=UserManagementCallback.create(
                level=9,
                operation=UserManagementOperation.REJECT_USER,
                user_id=user.id
            )
        )

    kb_builder.adjust(1)
    kb_builder.row(UserManagementCallback.create(level=6, filter=unpacked.filter, page=unpacked.page).get_back_button(6))

    return msg, kb_builder

# NEW: Level 8 - Approve User
@staticmethod
async def approve_user_handler(
    callback: CallbackQuery,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """Approve single user"""
    unpacked = UserManagementCallback.unpack(callback.data)
    admin_id = callback.from_user.id

    user = await UserRepository.approve_user(unpacked.user_id, admin_id, session)
    await session_commit(session)

    # Notify user
    await NotificationService.notify_user_approved(user.telegram_id)

    msg = Localizator.get_text(BotEntity.ADMIN, "user_approved_success").format(
        username=user.telegram_username or user.telegram_id
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(UserManagementCallback.create(level=6, filter=unpacked.filter).get_back_button(6))

    return msg, kb_builder

# NEW: Level 9 - Reject User: Request Reason (FSM State)
@staticmethod
async def reject_user_request_reason(
    callback: CallbackQuery,
    state: FSMContext
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Ask admin to enter rejection reason.
    Enters FSM state: UserManagementStates.rejection_reason
    """
    unpacked = UserManagementCallback.unpack(callback.data)
    user = await UserRepository.get_by_id(unpacked.user_id, session)

    # Store user_id in FSM for later
    await state.update_data(rejection_user_id=unpacked.user_id, rejection_filter=unpacked.filter)
    await state.set_state(UserManagementStates.rejection_reason)

    msg = Localizator.get_text(BotEntity.ADMIN, "reject_user_enter_reason").format(
        username=user.telegram_username or user.telegram_id
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(
        types.InlineKeyboardButton(
            text=Localizator.get_text(BotEntity.COMMON, "cancel"),
            callback_data=UserManagementCallback.create(
                level=7,
                user_id=unpacked.user_id,
                filter=unpacked.filter
            ).pack()
        )
    )

    return msg, kb_builder

# NEW: FSM Handler - Rejection Reason Text Input
@user_management.message(
    AdminIdFilter(),
    F.text,
    StateFilter(UserManagementStates.rejection_reason)
)
async def rejection_reason_preview(message: Message, state: FSMContext):
    """
    Admin entered rejection reason.
    Show preview with Edit/Send/Cancel buttons.
    """
    reason_text = message.text
    data = await state.get_data()
    user_id = data.get("rejection_user_id")

    # Store reason in FSM
    await state.update_data(rejection_reason_text=reason_text)

    # Show preview
    msg = Localizator.get_text(BotEntity.ADMIN, "reject_user_preview").format(
        reason=reason_text
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "send"),
        callback_data=UserManagementCallback.create(
            level=12,  # NEW: Execute rejection
            operation=UserManagementOperation.REJECT_USER_EXECUTE,
            user_id=user_id
        )
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "edit"),
        callback_data=UserManagementCallback.create(
            level=9,  # Back to reason input
            operation=UserManagementOperation.REJECT_USER,
            user_id=user_id
        )
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=UserManagementCallback.create(
            level=7,  # Back to user detail
            user_id=user_id
        )
    )
    kb_builder.adjust(1)

    await message.answer(msg, reply_markup=kb_builder.as_markup())

# NEW: Level 12 - Execute Rejection
@staticmethod
async def reject_user_execute(
    callback: CallbackQuery,
    state: FSMContext,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """Execute user rejection with reason from FSM"""
    unpacked = UserManagementCallback.unpack(callback.data)
    data = await state.get_data()
    reason = data.get("rejection_reason_text")
    rejection_filter = data.get("rejection_filter")
    admin_id = callback.from_user.id

    # Clear FSM state
    await state.clear()

    # Reject user
    user = await UserRepository.reject_user(unpacked.user_id, admin_id, reason, session)
    await session_commit(session)

    # Notify user
    await NotificationService.notify_user_rejected(user.telegram_id, reason)

    msg = Localizator.get_text(BotEntity.ADMIN, "user_rejected_success").format(
        username=user.telegram_username or user.telegram_id
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(UserManagementCallback.create(level=6, filter=rejection_filter).get_back_button(6))

    return msg, kb_builder

# NEW: Level 10 - Batch Approval Confirmation
@staticmethod
async def approve_batch_confirm(
    callback: CallbackQuery,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Confirmation dialog for batch approval.
    Asks: Send notifications? Yes/No/Cancel
    """
    unpacked = UserManagementCallback.unpack(callback.data)
    filter_type = unpacked.filter

    # Get all users in filter
    if filter_type == "waitlist":
        users = await UserRepository.get_all_by_status(ApprovalStatus.CLOSED_REGISTRATION, session)
    elif filter_type == "pending":
        users = await UserRepository.get_all_by_status(ApprovalStatus.PENDING, session)
    else:
        users = []

    count = len(users)

    msg = Localizator.get_text(BotEntity.ADMIN, "approve_batch_confirm").format(
        count=count,
        filter=filter_type
    )

    kb_builder = InlineKeyboardBuilder()

    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "yes_with_notification"),
        callback_data=UserManagementCallback.create(
            level=11,
            operation=UserManagementOperation.APPROVE_BATCH_EXECUTE,
            filter=filter_type,
            notify=1
        )
    )

    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "yes_silent"),
        callback_data=UserManagementCallback.create(
            level=11,
            operation=UserManagementOperation.APPROVE_BATCH_EXECUTE,
            filter=filter_type,
            notify=0
        )
    )

    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=UserManagementCallback.create(level=6, filter=filter_type)
    )

    kb_builder.adjust(1)

    return msg, kb_builder

# NEW: Level 11 - Execute Batch Approval
@staticmethod
async def approve_batch_execute(
    callback: CallbackQuery,
    session
) -> tuple[str, InlineKeyboardBuilder]:
    """Execute batch approval with optional notifications"""
    unpacked = UserManagementCallback.unpack(callback.data)
    filter_type = unpacked.filter
    send_notifications = unpacked.notify == 1
    admin_id = callback.from_user.id

    # Get all users
    if filter_type == "waitlist":
        users = await UserRepository.get_all_by_status(ApprovalStatus.CLOSED_REGISTRATION, session)
    elif filter_type == "pending":
        users = await UserRepository.get_all_by_status(ApprovalStatus.PENDING, session)
    else:
        users = []

    user_ids = [u.id for u in users]

    # Approve all
    count = await UserRepository.approve_batch(user_ids, admin_id, session)
    await session_commit(session)

    # Send notifications if requested
    if send_notifications:
        for user in users:
            try:
                await NotificationService.notify_user_approved(user.telegram_id)
            except Exception as e:
                logging.warning(f"Failed to notify user {user.telegram_id}: {e}")

    msg = Localizator.get_text(BotEntity.ADMIN, "batch_approval_success").format(
        count=count,
        notified="mit" if send_notifications else "ohne"
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(UserManagementCallback.create(level=6, filter=filter_type).get_back_button(6))

    return msg, kb_builder
```

---

### 5. Handlers

#### Update: `/start` Handler in `run.py`
```python
@main_router.message(Command(commands=["start", "help"]))
async def start(message: types.Message, session: AsyncSession | Session):
    # Get user language (fallback to bot default)
    user_lang_code = message.from_user.language_code
    # Check if user's language is supported (based on existing l10n files)
    user_lang = user_lang_code if user_lang_code in ["de", "en"] else None

    telegram_id = message.from_user.id

    # Create or get user
    user, status = await UserService.create_if_not_exist(
        UserDTO(
            telegram_username=message.from_user.username,
            telegram_id=telegram_id
        ),
        session
    )

    # Handle non-approved users
    if status == ApprovalStatus.PENDING:
        support_link = config.SUPPORT_LINK
        await message.answer(
            Localizator.get_text(BotEntity.USER, "registration_pending", lang=user_lang)
                .format(support_link=support_link)
        )
        return

    if status == ApprovalStatus.CLOSED_REGISTRATION:
        await message.answer(
            Localizator.get_text(BotEntity.USER, "registration_closed_waitlist", lang=user_lang)
        )
        return

    if status == ApprovalStatus.REJECTED:
        rejection_reason = user.rejection_reason or Localizator.get_text(
            BotEntity.USER, "rejection_reason_default", lang=user_lang
        )
        await message.answer(
            Localizator.get_text(BotEntity.USER, "registration_rejected", lang=user_lang)
                .format(reason=rejection_reason)
        )
        return

    # Normal flow for approved users (existing code)
    all_categories_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "all_categories", lang=user_lang))
    # ... (rest of existing /start code) ...
```

#### Update: `handlers/admin/user_management.py`
```python
# Add new levels to routing dict

levels = {
    0: user_management_menu,
    1: credit_management,
    2: level_2_router,
    3: level_3_router,
    4: level_4_router,
    5: lambda **kw: AdminService.get_user_list_filters(kw['session']),
    6: lambda **kw: AdminService.get_filtered_user_list(kw['callback'], kw['session']),
    7: lambda **kw: AdminService.get_user_detail_view(kw['callback'], kw['session']),
    8: lambda **kw: AdminService.approve_user_handler(kw['callback'], kw['session']),
    9: lambda **kw: AdminService.reject_user_request_reason(kw['callback'], kw['state']),  # FSM: Request reason
    10: lambda **kw: AdminService.approve_batch_confirm(kw['callback'], kw['session']),
    11: lambda **kw: AdminService.approve_batch_execute(kw['callback'], kw['session']),
    12: lambda **kw: AdminService.reject_user_execute(kw['callback'], kw['state'], kw['session']),  # Execute rejection
}

# NEW: FSM Handler (registered separately)
@user_management.message(AdminIdFilter(), F.text, StateFilter(UserManagementStates.rejection_reason))
async def rejection_reason_preview(message: Message, state: FSMContext):
    # ... (implementation in AdminService section above)
}
```

---

### 6. Callbacks

#### Update: `callbacks.py`
```python
class UserManagementOperation(str, Enum):
    # ... (existing operations) ...
    VIEW_USER_LIST = "view_user_list"
    VIEW_USER_DETAIL = "view_user_detail"
    APPROVE_USER = "approve_user"
    REJECT_USER = "reject_user"
    REJECT_USER_EXECUTE = "reject_user_execute"
    APPROVE_BATCH_CONFIRM = "approve_batch_confirm"
    APPROVE_BATCH_EXECUTE = "approve_batch_execute"

class UserManagementCallback(CallbackData, prefix="um"):
    level: int
    operation: UserManagementOperation | None = None
    user_id: int | None = None
    page: int | None = None
    filter: str | None = None  # "waitlist", "pending", "banned"
    notify: int | None = None  # 0=silent, 1=with notification
```

---

### 7. Localization (Neutral Voice, Passiv-Konstruktionen)

**Neue Keys in `l10n/de.json`:**
```json
{
  "registration_closed_waitlist": "Shop akzeptiert derzeit keine neuen Registrierungen. Aufnahme auf Warteliste erfolgt. Benachrichtigung wird versendet, sobald Plätze verfügbar sind.",
  "registration_pending": "Account wartet auf Freischaltung. Kontakt zum Support zur Vorstellung erforderlich: {support_link}",
  "registration_rejected": "Registrierung wurde abgelehnt.\n\nGrund: {reason}",
  "rejection_reason_default": "Keine weiteren Informationen verfügbar.",
  "registration_approved_notification": "Account wurde freigeschaltet. Willkommen!",

  "user_list": "Benutzerliste",
  "user_list_filters": "Benutzerliste - Filter auswählen",
  "filter_waitlist": "⏳ Warteliste ({count})",
  "filter_pending": "🕐 Wartend ({count})",
  "filter_banned": "🚫 Gebannt ({count})",
  "user_list_header": "Benutzerliste - Filter: {filter}\nSeite {page}/{total_pages} ({total_users} Benutzer gesamt)",

  "user_detail": "Benutzer: @{username}\nID: {user_id}\nRegistrierung: {registered_at}\nStatus: {status}\n\nStatistiken:\n💰 Gesamtumsatz: {total_revenue}\n📦 Anzahl Bestellungen: {total_orders}\n📅 Erste Bestellung: {first_order}\n📅 Letzte Bestellung: {last_order}",

  "contact_user": "✉️ Benutzer kontaktieren",
  "approve_user": "✅ Freischalten",
  "reject_user": "❌ Ablehnen",
  "approve_all_batch": "✅ Alle freischalten",

  "approve_batch_confirm": "Gesamte Liste freischalten?\n\nAnzahl Benutzer: {count}\nFilter: {filter}\n\nBenachrichtigung an alle Benutzer senden?",
  "yes_with_notification": "Ja, mit Benachrichtigung",
  "yes_silent": "Ja, ohne Benachrichtigung",
  "cancel": "Abbrechen",

  "user_approved_success": "Benutzer @{username} wurde freigeschaltet.",
  "batch_approval_success": "{count} Benutzer wurden freigeschaltet ({notified} Benachrichtigung).",

  "reject_user_enter_reason": "Ablehnungsgrund für @{username} eingeben:",
  "reject_user_preview": "Folgende Nachricht wird an Benutzer gesendet:\n\n{reason}\n\nBestätigen?",
  "user_rejected_success": "Benutzer @{username} wurde abgelehnt.",
  "send": "✅ Senden",
  "edit": "✏️ Bearbeiten"
}
```

**Gleiche Keys in `l10n/en.json` (englisch, neutral voice)**

---

### 8. Notifications

#### Update: `services/notification.py`
```python
@staticmethod
async def notify_pending_approval(user: UserDTO):
    """Notify admins about new pending user registration"""
    message = f"🆕 Neue Registrierung (wartet auf Freischaltung)\n\n"
    message += f"Benutzername: @{user.telegram_username or 'N/A'}\n"
    message += f"ID: {user.telegram_id}"
    await NotificationService.send_to_admins(message)

@staticmethod
async def notify_user_approved(user_id: int, user_lang: str = None):
    """Notify user about registration approval"""
    bot = get_bot()
    await bot.send_message(
        chat_id=user_id,
        text=Localizator.get_text(
            BotEntity.USER,
            "registration_approved_notification",
            lang=user_lang
        )
    )

@staticmethod
async def notify_user_rejected(user_id: int, reason: str, user_lang: str = None):
    """Notify user about registration rejection with reason"""
    bot = get_bot()
    await bot.send_message(
        chat_id=user_id,
        text=Localizator.get_text(
            BotEntity.USER,
            "registration_rejected",
            lang=user_lang
        ).format(reason=reason)
    )
```

---

### 9. Migration

**Neue Alembic Migration: `add_registration_management.py`**
```python
"""add registration management system

Revision ID: xxxxx
Revises: yyyyy
Create Date: 2025-12-01
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. Create system_settings table
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # 2. Add approval fields to users
    op.add_column('users', sa.Column('approval_status', sa.String(), server_default='approved'))
    op.add_column('users', sa.Column('approval_requested_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('approved_by_admin_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('rejection_reason', sa.String(), nullable=True))

    # 3. Add user statistics fields (DUMMY values for now)
    # TODO: Implement real aggregation in Trust-Level System
    op.add_column('users', sa.Column('lifetime_revenue', sa.Float(), server_default='0.0'))
    op.add_column('users', sa.Column('lifetime_orders', sa.Integer(), server_default='0'))
    op.add_column('users', sa.Column('first_order_date', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_order_date', sa.DateTime(), nullable=True))

    # 4. Set default registration_mode
    op.execute("INSERT INTO system_settings (key, value) VALUES ('registration_mode', 'open')")

    # 5. Set all existing users to approved with their registered_at as approved_at
    op.execute("""
        UPDATE users
        SET approval_status = 'approved',
            approved_at = registered_at
        WHERE approval_status IS NULL OR approval_status = ''
    """)

def downgrade():
    # Remove user statistics fields
    op.drop_column('users', 'last_order_date')
    op.drop_column('users', 'first_order_date')
    op.drop_column('users', 'lifetime_orders')
    op.drop_column('users', 'lifetime_revenue')

    # Remove approval fields
    op.drop_column('users', 'rejection_reason')
    op.drop_column('users', 'approved_by_admin_id')
    op.drop_column('users', 'approved_at')
    op.drop_column('users', 'approval_requested_at')
    op.drop_column('users', 'approval_status')

    # Drop system_settings table
    op.drop_table('system_settings')
```

---

### 10. Configuration Validation

**Update: `utils/config_validator.py`**
```python
def validate_registration_mode():
    """
    Validate SUPPORT_LINK is set when registration mode requires it.
    Called during bot startup AFTER SystemSettings table exists.
    """
    # This check happens after DB is initialized
    # TODO: Add to startup sequence in run.py
    pass  # Will be validated runtime when mode is read
```

---

## Implementation Order

1. **Enums** (ApprovalStatus) - 5 Min
2. **Database** (models + migration) - 15 Min
3. **Repositories** (system_settings + user extensions) - 25 Min
4. **Callbacks** (UserManagementOperation erweitern) - 5 Min
5. **FSM States** (UserManagementStates.rejection_reason) - 3 Min
6. **Services** (user.py + admin.py) - 40 Min (includes rejection FSM)
7. **Handlers** (/start + user_management levels + FSM handler) - 25 Min
8. **Localization** (keys) - 10 Min
9. **Notifications** (approve/reject) - 5 Min
10. **Testing** (manual flows including rejection) - 25 Min

**Total: ~158 Minuten**

---

## Testing Plan

### 1. Registration Modes
- [ ] Mode "open": Neuer User → sofort approved, sieht Shop
- [ ] Mode "request_approval": Neuer User → pending message mit Support-Link
- [ ] Mode "closed": Neuer User → waitlist message
- [ ] SUPPORT_LINK fehlt + approval mode → ConfigurationError

### 2. User List & Filters
- [ ] Admin öffnet User Management → "User List" Button sichtbar
- [ ] Filter "Warteliste" zeigt korrekte Counts
- [ ] Filter "Wartend" zeigt pending users
- [ ] Filter "Gebannt" zeigt blocked users
- [ ] Pagination funktioniert (config.PAGE_ENTRIES=8)

### 3. User Detail View
- [ ] Zeigt Username (oder ID-Fallback)
- [ ] Zeigt Registrierungsdatum, Status
- [ ] DUMMY Stats angezeigt (TODO-Hinweis)
- [ ] Kontaktbutton öffnet Telegram Chat
- [ ] Approve/Reject Buttons je nach Status

### 4. Batch Operations
- [ ] "Alle freischalten" Button nur bei waitlist/pending
- [ ] Confirmation Dialog: 3 Optionen (Ja/Ja still/Cancel)
- [ ] Notification wird versendet (wenn gewählt)
- [ ] Alle User auf "approved" gesetzt

### 5. Einzeln Approve/Reject
- [ ] User approven → Status updated, Notification gesendet
- [ ] User rejecten → TODO: FSM für Reason-Input

### 6. Bestehende User
- [ ] Bestehende User (approval_status="approved") können weiterhin alles nutzen
- [ ] Username-Update funktioniert bei /start

---

## Related TODOs

**Erstelle vor Implementation:**
- `TODO/2025-12-01_TODO_user-trust-level-system.md` - User Statistics Aggregation & Trust-Level Scoring

**Abhängigkeiten:**
- Keine (standalone feature)

---

## Notes

- **User Statistics:** Aktuell DUMMY-Werte (0, NULL). Separate TODO für Trust-Level System.
- **Rejection FSM:** Level 9 (Reject User) braucht FSM-State für Reason-Input. Implementiere später oder als Sub-TODO.
- **"All Users" Filter:** Aktuell nicht implementiert (könnte sehr groß werden). Später mit Server-Side-Search.
- **Performance:** Bei >1000 Users sollte "Alle freischalten" gecancelt werden. Add confirmation mit Count-Limit.

---

**Status:** 🟢 Ready to implement
