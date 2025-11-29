# TODO: Implement Telegram Timestamp Formatting

## Problem
Currently, datetime values in Telegram messages are sent as pre-formatted strings (e.g., `"2025-11-29 12:00"`). This means all users see the same time regardless of their timezone, typically UTC or server time.

## Solution
Use Telegram's built-in timestamp formatting feature that automatically converts Unix timestamps to each user's local timezone.

### Current Implementation
```python
date = datetime.now().strftime("%Y-%m-%d %H:%M")  # → "2025-11-29 12:00"
message = f"Created: {date}"
```

### Proposed Implementation
```python
timestamp = int(datetime.now(timezone.utc).timestamp())
message = f"Created: <t:{timestamp}:f>"  # Telegram auto-converts to user's TZ
```

## Telegram Timestamp Formats
- `<t:TIMESTAMP:t>` - Short time (e.g., "16:20")
- `<t:TIMESTAMP:T>` - Long time (e.g., "16:20:30")
- `<t:TIMESTAMP:d>` - Short date (e.g., "20/04/2021")
- `<t:TIMESTAMP:D>` - Long date (e.g., "20 April 2021")
- `<t:TIMESTAMP:f>` - Short date/time (e.g., "20 April 2021 16:20")
- `<t:TIMESTAMP:F>` - Long date/time (e.g., "Tuesday, 20 April 2021 16:20")
- `<t:TIMESTAMP:R>` - Relative time (e.g., "2 hours ago")

## Benefits
- Automatic timezone conversion for each user
- No server-side timezone configuration needed
- Consistent user experience across different regions
- Native Telegram feature (no external dependencies)

## Implementation Steps
1. Create utility function `format_datetime_for_telegram(dt: datetime, style: str = 'f') -> str`
2. Update `invoice_formatter.py` to use Telegram timestamps instead of `.strftime()`
3. Update all other locations using datetime formatting in messages:
   - Order notifications
   - Payment confirmations
   - Shipping notifications
   - Cancellation messages
4. Test with users in different timezones
5. Update documentation

## Files to Modify
- `services/invoice_formatter.py` - Multiple `.strftime()` calls
- `services/notification.py` - Notification timestamps
- `utils/` - New utility function for Telegram timestamp formatting

## Priority
Medium - Improves UX for international users but not critical for functionality

## Estimated Effort
2-3 hours (implement utility, update formatters, test)