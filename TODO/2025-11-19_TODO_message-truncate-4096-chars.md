# Message Truncate/Split for Telegram 4096 Character Limit

**Date:** 2025-11-19
**Priority:** Medium
**Estimated Effort:** Medium (1-2 hours)

---

## Description
Implement message truncation or splitting for user-facing messages that exceed Telegram's 4096 character limit. Currently, messages that exceed this limit fail silently - the user receives no message at all.

## Problem
- Telegram API throws `TelegramBadRequest: Message is too long` for messages >4096 chars
- No length validation exists for user messages (only admin notifications send files)
- Large carts with multiple tiered items can approach or exceed this limit
- User experience: Silent failure - checkout message doesn't appear

## Current Behavior
In `bot.py:215-218`, admin notifications handle this by sending text files:
```python
if len(admin_notification) > 4096:
    byte_array = bytearray(admin_notification, 'utf-8')
    admin_notification = BufferedInputFile(byte_array, "exception.txt")
```

User messages have no such handling.

## Acceptance Criteria
- [ ] Detect when user message exceeds 4096 characters
- [ ] Choose truncation strategy:
  - Option A: Split into multiple messages (items list + invoice)
  - Option B: Truncate with "Mehr anzeigen" deep link
  - Option C: Send as file for very long messages (like admin notifications)
- [ ] Implement chosen strategy in affected handlers:
  - `handlers/user/cart.py` (checkout confirmation)
  - `handlers/user/order.py` (order details)
  - `services/invoice_formatter.py` (formatting layer)
- [ ] Preserve inline keyboard buttons when splitting/truncating
- [ ] Test with large carts (8+ tiered items, 5+ tiers each)

## Files Affected
- `services/invoice_formatter.py:955-1040` (format_checkout_summary)
- `handlers/user/cart.py` (checkout flow)
- Potentially create utility: `utils/message_splitter.py`

## Technical Notes
- UTF-8 encoding: Some characters count as multiple bytes
- Inline keyboards must stay with last message chunk
- Consider preserving HTML formatting across splits
- Message order matters (send sequentially, not parallel)

## References
- Codex finding: `services/invoice_formatter.py:955-1040`
- Admin notification pattern: `bot.py:215-218`
- Telegram Bot API: https://core.telegram.org/bots/api#sendmessage (text length limit)

## Decision
Priority: Medium - Only occurs with large carts, but impacts UX significantly when it does.
Recommended approach: Option A (split into multiple messages) for better UX.
