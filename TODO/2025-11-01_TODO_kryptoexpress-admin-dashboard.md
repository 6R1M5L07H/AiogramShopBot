# KryptoExpress Balance in Admin Dashboard

**Date:** 2025-11-01
**Priority:** Medium
**Status:** Planning
**Estimated Effort:** 3-4 hours
**Category:** Admin Features / Payment System

---

## Overview

Display merchant wallet balances from KryptoExpress API in the admin dashboard, providing real-time visibility into available crypto funds.

**Current State:**
- No visibility into KryptoExpress wallet balances
- Admins must log into KryptoExpress dashboard separately
- No unified view of bot finances

**Desired State:**
- Real-time balance display in admin menu
- Multiple crypto wallet balances (BTC, ETH, LTC, SOL, BNB, USDT, USDC)
- Quick overview without leaving Telegram
- Historical balance tracking (optional)

---

## User Story

**As an** admin
**I want to** see KryptoExpress wallet balances directly in the bot
**So that** I can monitor finances without switching platforms

---

## Acceptance Criteria

### Must Have
- [ ] Admin menu shows "💰 Wallet Balances" button
- [ ] Balance screen displays all crypto wallets
- [ ] Shows both crypto amount and EUR equivalent
- [ ] Data fetched from KryptoExpress API
- [ ] Handles API errors gracefully
- [ ] Refresh button to update balances
- [ ] Last updated timestamp

### Should Have
- [ ] Cache balances for 5 minutes (reduce API calls)
- [ ] Visual indicators (low balance warnings)
- [ ] Total balance in EUR across all wallets
- [ ] Localized currency display (EN/DE)

### Could Have
- [ ] Historical balance chart (7/30 days)
- [ ] Export balance report (CSV)
- [ ] Balance change alerts (Telegram notifications)
- [ ] Withdrawal suggestions (if balance too high)

---

## Technical Specification

### API Integration

**KryptoExpress API Endpoint:**
```python
GET /api/v1/merchant/balances
Headers:
  X-Api-Key: {KRYPTO_EXPRESS_API_KEY}
  X-Api-Secret: {KRYPTO_EXPRESS_API_SECRET}

Response:
{
  "balances": [
    {
      "currency": "BTC",
      "available": "0.05432100",
      "locked": "0.00120000",
      "eur_value": "2450.50"
    },
    {
      "currency": "ETH",
      "available": "1.23456789",
      "locked": "0.05000000",
      "eur_value": "3890.25"
    },
    ...
  ],
  "total_eur": "12340.75",
  "last_updated": "2025-11-01T15:30:00Z"
}
```

### Implementation

#### 1. Admin Service Method

**File:** `services/admin.py`

```python
@staticmethod
async def get_wallet_balances() -> tuple[str, InlineKeyboardBuilder]:
    """
    Fetch and display KryptoExpress wallet balances.

    Returns:
        Tuple of (message_text, keyboard)
    """
    from crypto_api.CryptoApiWrapper import CryptoApiWrapper
    import config

    # Fetch balances from KryptoExpress
    headers = {
        "X-Api-Key": config.KRYPTO_EXPRESS_API_KEY,
        "X-Api-Secret": config.KRYPTO_EXPRESS_API_SECRET
    }

    try:
        response = await CryptoApiWrapper.fetch_api_request(
            f"{config.KRYPTO_EXPRESS_API_URL}/merchant/balances",
            method="GET",
            headers=headers
        )

        balances = response.get("balances", [])
        total_eur = response.get("total_eur", 0.0)
        last_updated = response.get("last_updated")

        # Format message
        message_text = (
            f"💰 <b>{Localizator.get_text(BotEntity.ADMIN, 'wallet_balances_title')}</b>\n\n"
        )

        for balance in balances:
            currency = balance["currency"]
            available = balance["available"]
            locked = balance.get("locked", "0.00")
            eur_value = balance["eur_value"]

            # Emoji per currency
            emoji = {
                "BTC": "₿",
                "ETH": "Ξ",
                "LTC": "Ł",
                "SOL": "◎",
                "BNB": " ",
                "USDT": "₮",
                "USDC": "💵"
            }.get(currency, "💰")

            message_text += (
                f"{emoji} <b>{currency}</b>\n"
                f"  Available: <code>{available}</code>\n"
            )

            if float(locked) > 0:
                message_text += f"  Locked: <code>{locked}</code>\n"

            message_text += f"  Value: {Localizator.get_currency_symbol()}{eur_value}\n\n"

        message_text += (
            f"<b>{Localizator.get_text(BotEntity.ADMIN, 'total_balance')}</b>\n"
            f"{Localizator.get_currency_symbol()}{total_eur:.2f}\n\n"
            f"<i>{Localizator.get_text(BotEntity.ADMIN, 'last_updated')}: {last_updated}</i>"
        )

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "refresh_balances"),
            callback_data=AdminMenuCallback.create(level=99)  # Refresh balances
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=AdminMenuCallback.create(level=0)
        )
        kb_builder.adjust(1)

        return message_text, kb_builder

    except Exception as e:
        logging.error(f"Failed to fetch KryptoExpress balances: {e}")

        message_text = (
            f"  <b>{Localizator.get_text(BotEntity.ADMIN, 'balance_fetch_error')}</b>\n\n"
            f"{Localizator.get_text(BotEntity.ADMIN, 'balance_fetch_error_desc')}\n\n"
            f"<code>{str(e)}</code>"
        )

        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=AdminMenuCallback.create(level=0)
        )

        return message_text, kb_builder
```

#### 2. Admin Handler

**File:** `handlers/admin/admin.py`

```python
# Add to admin menu
async def admin(**kwargs):
    # ... existing code ...

    admin_menu_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "wallet_balances"),
        callback_data=AdminMenuCallback.create(level=5)
    )

    # ... rest of menu ...

# Add navigation handler
@admin_router.callback_query(AdminIdFilter(), AdminMenuCallback.filter())
async def admin_menu_navigation(...):
    current_level = callback_data.level

    levels = {
        0: admin,
        5: show_wallet_balances,  # NEW
        99: refresh_wallet_balances,  # NEW
    }

    # ...

async def show_wallet_balances(**kwargs):
    callback = kwargs.get("callback")
    msg, kb_builder = await AdminService.get_wallet_balances()
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())

async def refresh_wallet_balances(**kwargs):
    # Same as show_wallet_balances, but clears cache first
    callback = kwargs.get("callback")

    # Clear cache (if implemented)
    # await clear_balance_cache()

    await callback.answer(
        Localizator.get_text(BotEntity.ADMIN, "refreshing_balances"),
        show_alert=False
    )

    msg, kb_builder = await AdminService.get_wallet_balances()
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
```

#### 3. Localization

**File:** `l10n/en.json`

```json
"admin": {
  "wallet_balances": "💰 Wallet Balances",
  "wallet_balances_title": "KryptoExpress Wallet Balances",
  "total_balance": "Total Balance (EUR)",
  "last_updated": "Last Updated",
  "refresh_balances": "  Refresh",
  "balance_fetch_error": "Error Fetching Balances",
  "balance_fetch_error_desc": "Could not retrieve balances from KryptoExpress. Please try again later.",
  "refreshing_balances": "Refreshing balances..."
}
```

**File:** `l10n/de.json`

```json
"admin": {
  "wallet_balances": "💰 Guthaben",
  "wallet_balances_title": "KryptoExpress Wallet-Guthaben",
  "total_balance": "Gesamtguthaben (EUR)",
  "last_updated": "Zuletzt aktualisiert",
  "refresh_balances": "  Aktualisieren",
  "balance_fetch_error": "Fehler beim Abrufen der Guthaben",
  "balance_fetch_error_desc": "Guthaben konnten nicht von KryptoExpress abgerufen werden. Bitte versuchen Sie es später erneut.",
  "refreshing_balances": "Guthaben werden aktualisiert..."
}
```

#### 4. Optional: Redis Cache

**File:** `utils/balance_cache.py`

```python
"""Balance caching to reduce API calls."""

import json
from typing import Optional
from redis.asyncio import Redis

CACHE_KEY = "kryptoexpress:balances"
CACHE_TTL = 300  # 5 minutes

async def get_cached_balances(redis: Redis) -> Optional[dict]:
    """Get cached balances from Redis."""
    cached = await redis.get(CACHE_KEY)
    if cached:
        return json.loads(cached)
    return None

async def cache_balances(redis: Redis, balances: dict):
    """Cache balances in Redis."""
    await redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(balances))

async def clear_balance_cache(redis: Redis):
    """Clear cached balances (for manual refresh)."""
    await redis.delete(CACHE_KEY)
```

---

## Message Format Example

```
💰 KryptoExpress Wallet Balances

₿ BTC
  Available: 0.05432100
  Locked: 0.00120000
  Value: €2,450.50

Ξ ETH
  Available: 1.23456789
  Locked: 0.05000000
  Value: €3,890.25

Ł LTC
  Available: 12.34567890
  Value: €1,234.50

◎ SOL
  Available: 45.67890123
  Value: €3,456.80

  BNB
  Available: 8.90123456
  Value: €1,308.70

Total Balance (EUR)
€12,340.75

Last Updated: 2025-11-01 15:30:00 UTC
```

---

## Error Handling

### 1. API Timeout
```
  Error Fetching Balances

Could not retrieve balances from KryptoExpress. Please try again later.

Timeout after 30 seconds
```

### 2. Authentication Error
```
  Error Fetching Balances

API authentication failed. Please check your API credentials in .env

401 Unauthorized
```

### 3. Network Error
```
  Error Fetching Balances

Network error. Please check your internet connection.

Connection refused
```

---

## Testing Checklist

### Manual Tests
- [ ] Admin sees "Wallet Balances" button in menu
- [ ] Click button → Balances load successfully
- [ ] All cryptocurrencies displayed with correct emojis
- [ ] EUR values calculated correctly
- [ ] Total balance sum is correct
- [ ] "Refresh" button updates balances
- [ ] "Back" button returns to admin menu

### Error Tests
- [ ] Invalid API key → Shows error message
- [ ] KryptoExpress API down → Shows error message
- [ ] Network timeout → Shows error message
- [ ] Malformed response → Shows error message

### Performance Tests
- [ ] Balance fetch < 3 seconds
- [ ] Cache reduces API calls (if implemented)
- [ ] Multiple admins can view simultaneously

---

## Security Considerations

### API Credentials
-   API keys stored in .env (not hardcoded)
-   Keys masked in logs (secret masking filter)
-   HTTPS only for API calls
-   Admin-only access (AdminIdFilter)

### Data Protection
- ℹ️ Balances not stored in database (fetched on-demand)
- ℹ️ Cache expires after 5 minutes (if implemented)
- ℹ️ No balance logging (privacy)

---

## Dependencies

### Existing Infrastructure
-   KryptoExpress API wrapper (CryptoApiWrapper)
-   Admin authentication (AdminIdFilter)
-   Localization system (Localizator)
-   Callback routing (AdminMenuCallback)

### New Dependencies
- None (uses existing infrastructure)

---

## Implementation Order

1. **Phase 1: Basic Display** (2 hours)
   - [ ] Add AdminService.get_wallet_balances()
   - [ ] Add admin menu button
   - [ ] Add navigation handler
   - [ ] Add localization strings
   - [ ] Test basic display

2. **Phase 2: Error Handling** (30 minutes)
   - [ ] Handle API errors
   - [ ] Handle timeout
   - [ ] Handle authentication errors
   - [ ] User-friendly error messages

3. **Phase 3: Refresh & Cache** (1 hour)
   - [ ] Add refresh button
   - [ ] Implement Redis caching
   - [ ] Add cache expiry
   - [ ] Add cache clear on refresh

4. **Phase 4: Polish** (30 minutes)
   - [ ] Format currencies properly
   - [ ] Add emojis per crypto
   - [ ] Improve layout
   - [ ] Test with real data

---

## Future Enhancements

### Phase 2 (Future)
- [ ] Historical balance tracking (database)
- [ ] Balance change notifications
- [ ] Low balance alerts (< €100)
- [ ] CSV export of balance history
- [ ] Balance chart (matplotlib)

### Phase 3 (Future)
- [ ] Withdrawal suggestions
- [ ] Auto-convert to stablecoins
- [ ] Multi-merchant support (if multiple shops)

---

## Related Features

- Payment System (uses KryptoExpress)
- Admin Statistics (could integrate balance data)
- Financial Reporting (could use balance history)

---

## Notes

- Balance display is read-only (no withdrawals from bot)
- Withdrawals must be done via KryptoExpress dashboard
- Consider rate limiting API calls (max 1/minute per admin)
- Cache reduces load on KryptoExpress API

---

## Success Metrics

- [ ] Admins can view balances in < 3 seconds
- [ ] No need to open KryptoExpress dashboard for balance checks
- [ ] Reduced support requests about balance visibility
- [ ] API error rate < 1%

---

**Status:** Ready for Implementation
**Estimated Timeline:** 1-2 days (including testing)
