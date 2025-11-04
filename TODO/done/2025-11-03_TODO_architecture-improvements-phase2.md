# Architecture Improvements - Phase 2

**Date:** 2025-11-03
**Branch:** technical-debt-3
**Priority:** HIGH
**Estimated Effort:** 4-6 hours
**Source:** Security Code Review

---

## Overview

Architecture and design issues identified in code review:
1. Config side-effects at import time
2. Service/UI layer mixing
3. Bot dependency injection issues

---

## Task 1: Config Side-Effects (Lazy Initialization)

**Problem:**
```python
# config.py - Executes on import!
if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
    WEBHOOK_HOST = start_ngrok()  # Side effect: starts ngrok process
else:
    WEBHOOK_HOST = get_sslipio_external_url()  # Side effect: HTTP request
```

Side effects on import:
- ngrok process starts when importing config
- HTTP request to sslipio.com on import
- Makes testing difficult (can't mock)
- Violates "import should be safe" principle

**Solution:**
- Create lazy initialization functions
- Move side effects to explicit startup phase
- Only execute when actually needed

**Files to modify:**
- `config.py` - Remove side effects from module level
- `bot.py` - Add explicit initialization in startup
- `ngrok_executor.py` - Already functional (keep as utility)
- `external_ip.py` - Already functional (keep as utility)

**Implementation:**
```python
# config.py
WEBHOOK_HOST = None  # Will be initialized in startup

def initialize_webhook_config():
    """Initialize webhook configuration with side effects."""
    global WEBHOOK_HOST, WEBHOOK_URL

    if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
        WEBHOOK_HOST = start_ngrok()
    elif RUNTIME_ENVIRONMENT == RuntimeEnvironment.PROD:
        WEBHOOK_HOST = get_sslipio_external_url()

    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    return WEBHOOK_URL
```

**Acceptance Criteria:**
- Importing config.py does NOT start ngrok or make HTTP requests
- Webhook config initialized explicitly in bot.py startup
- Tests can import config without side effects
- Bot still works exactly as before

---

## Task 2: Service/UI Separation

**Problem:**
```python
# services/notification.py
@staticmethod
async def make_user_button(username: str | None) -> InlineKeyboardMarkup:
    # Service layer creating UI elements!
    user_button_builder = InlineKeyboardBuilder()
    if username:
        user_button_inline = types.InlineKeyboardButton(text=username, url=f"https://t.me/{username}")
        user_button_builder.add(user_button_inline)
    return user_button_builder.as_markup()
```

Services should NOT create keyboards or buttons - that's UI layer responsibility.

**Solution:**
- Keep services focused on business logic
- Move keyboard/button creation to handlers
- Services return data, handlers create UI

**Files to audit:**
- `services/notification.py` - Remove make_user_button()
- `services/admin.py` - Check for keyboard creation
- `services/order.py` - Check for UI elements
- `handlers/admin/*.py` - Move UI logic here

**Refactoring strategy:**
1. Identify all places where services create keyboards/buttons
2. Change service methods to return data only
3. Let handlers create keyboards from that data

**Acceptance Criteria:**
- No InlineKeyboardBuilder in services/
- No types.InlineKeyboardButton in services/
- Services return pure data (DTOs, lists, dicts)
- Handlers responsible for all UI creation

---

## Task 3: Bot Dependency Injection

**Problem:**
```python
# services/notification.py
@staticmethod
async def send_to_admins(message: str, reply_markup):
    bot = Bot(token=TOKEN, default=DefaultBotProperties(...))  # Creates new bot instance!
    for admin_id in ADMIN_ID_LIST:
        await bot.send_message(admin_id, message, reply_markup=reply_markup)
    await bot.session.close()  # Manual cleanup
```

Issues:
- New Bot instance for every notification
- Wasteful (new HTTP session each time)
- Manual session management (easy to leak)
- Hard to test (can't mock the bot)

**Solution:**
- Pass bot instance as parameter
- Use dependency injection pattern
- Reuse existing bot instance from bot.py
- Or use a singleton pattern for bot instance

**Option A: Dependency Injection (Preferred)**
```python
# services/notification.py
@staticmethod
async def send_to_admins(bot: Bot, message: str, reply_markup):
    for admin_id in ADMIN_ID_LIST:
        await bot.send_message(admin_id, message, reply_markup=reply_markup)
    # No session management - caller handles it
```

**Option B: Singleton Pattern**
```python
# bot_instance.py (new file)
_bot_instance = None

def get_bot() -> Bot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(token=TOKEN, default=DefaultBotProperties(...))
    return _bot_instance
```

**Files to modify:**
- `services/notification.py` - Remove bot creation, add bot parameter
- `services/admin.py` - Check for bot creation
- All handlers calling notification services - Pass bot instance

**Acceptance Criteria:**
- No `Bot(token=TOKEN, ...)` in services/
- Services accept bot as parameter OR use singleton
- No manual session.close() in services
- All tests can inject mock bot

---

## Testing Plan

### Manual Testing
1. **Config Lazy Init:**
   - Import config in Python shell → should NOT start ngrok
   - Start bot → should start ngrok and set WEBHOOK_URL
   - Check logs for correct initialization order

2. **Service/UI Separation:**
   - Trigger admin notification with username
   - Verify user button still appears
   - Check that service code has no keyboard logic

3. **Bot Injection:**
   - Send test notification
   - Check logs: should NOT see multiple "Bot initialized" messages
   - Verify notifications still work

### Automated Testing
- Add unit test for config lazy init
- Add test that services don't import UI classes
- Mock bot injection in notification tests

---

## Migration Strategy

**Order of implementation:**
1. Start with Task 3 (Bot DI) - smallest scope, easy to test
2. Then Task 2 (Service/UI) - medium complexity
3. Finally Task 1 (Config) - highest risk, do last

**Backward compatibility:**
- All changes should be internal refactoring
- External behavior must remain identical
- No breaking changes to handlers

---

## Rollback Plan

If issues occur:
```bash
git checkout develop
git branch -D technical-debt-3
```

All changes are architectural refactoring, no data model changes.

---

## Success Criteria

- [ ] Config import has no side effects
- [ ] Services contain zero UI code
- [ ] Bot instance reused across notifications
- [ ] All existing functionality still works
- [ ] Tests pass
- [ ] Manual testing confirms no regressions

---

## Next Steps (Phase 3)

After Phase 2 merge:
- Heavy service method refactoring
- Further separation of concerns
- Performance optimizations

---

**Status:** READY TO START
**Owner:** Developer
**Reviewer:** Required before merge
