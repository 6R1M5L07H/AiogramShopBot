# TODO: Telegram Message Splitting for 4096 Character Limit

**Created:** 2025-11-29
**Status:** 🟢 Open
**Priority:** MEDIUM (Technical Debt / UX)
**Estimated Effort:** 2-3 hours
**Origin:** Issue #22 from Security Architecture Findings

---

## Problem Statement

The invoice formatter builds single mega-messages with tier breakdowns, positions, totals, and savings. Larger carts (50+ items or complex tier structures) hit Telegram's 4096 character limit, causing:

- Message truncation
- Inline action buttons not displaying
- UX degradation for large orders

**Affected Locations:**
- `services/invoice_formatter.py:955-1040` (primary)
- Any service that builds large notification messages

---

## Solution: Recursive Message Splitting

Implement a robust message-splitting utility that:

1. **Detects Length**: Check if message exceeds 4096 characters
2. **Splits Intelligently**: Break at natural boundaries (sentences, paragraphs, sections)
3. **Preserves Formatting**: Maintain HTML tags across splits
4. **Recursive Splitting**: If a split segment is still too long, split again
5. **Sequential Sending**: Send messages in order with small delays

### Implementation Steps

#### 1. Create Message Splitting Utility

**File:** `utils/message_splitter.py`

**Core Functions:**
```python
def split_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Split a long message into chunks that fit Telegram's limit.

    Args:
        text: The full message text (with HTML formatting)
        max_length: Maximum length per chunk (default: 4000 for safety margin)

    Returns:
        List of message chunks, each <= max_length

    Features:
        - Splits at paragraph boundaries (\n\n) first
        - Falls back to sentence boundaries (. or ! or ?)
        - Preserves HTML tags across splits
        - Handles code blocks (<code>, <pre>) specially
        - Adds continuation indicators ("..." / "continued...")
        - Recursive splitting for oversized segments
    """
    pass

def send_split_messages(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    delay_ms: int = 500
) -> list[Message]:
    """
    Send a potentially long message as multiple messages.

    Args:
        bot: Telegram Bot instance
        chat_id: Target chat ID
        text: Full message text
        reply_markup: Buttons (attached to LAST message only)
        delay_ms: Delay between messages in milliseconds

    Returns:
        List of sent Message objects
    """
    pass
```

#### 2. Integration Points

**Primary:**
- `services/invoice_formatter.py`: Wrap all `format_*` methods
- `services/notification.py`: Use for admin broadcasts and user notifications

**Secondary (if needed):**
- `services/order.py`: Order details
- `services/cart.py`: Large cart displays
- `handlers/admin/admin.py`: Statistics messages

#### 3. Testing Strategy

**Unit Tests:** `tests/utils/test_message_splitter.py`

Test cases:
- Short message (< 4096) → no split
- Long message (> 4096) → splits at paragraph
- Message with code blocks → preserves formatting
- Message with HTML tags → tags not broken
- Oversized paragraph (> 4096) → recursive split
- Edge case: 8000 char message → 2 chunks
- Edge case: 12000 char message → 3 chunks

**Integration Tests:**
- Generate invoice with 50+ items
- Verify all messages sent successfully
- Verify buttons attached to last message only
- Verify no message exceeds 4096 chars

**Manual Tests:**
- Create cart with 100 items
- Trigger checkout → verify multiple messages
- Create order with 50+ tier items
- Cancel order → verify cancellation notification splits correctly

---

## Design Decisions

### Why Recursive Splitting (Option A)?

**Rejected Alternatives:**
1. **Truncation** - Loses data, confusing for users
2. **Pagination** - Requires state management, complex UX
3. **Summary + Detail Button** - Just moves the problem
4. **File Attachment** - Poor mobile UX, extra step

**Why Recursive Splitting Wins:**
- No data loss
- No user interaction required
- Works for any message size
- Simple implementation
- Backward compatible (no schema changes)

### Split Priority

1. **Paragraph boundaries** (`\n\n`) - Natural reading breaks
2. **Sentence boundaries** (`. `, `! `, `? `) - Maintains context
3. **Word boundaries** (` `) - Last resort

### Special Handling

- **Code blocks** (`<code>`, `<pre>`): Never split mid-block
- **HTML tags**: Close tags before split, reopen after
- **Tier tables**: Keep tier header with prices
- **Totals section**: Keep together when possible

---

## Implementation Checklist

### Phase 1: Utility Implementation
- [ ] Create `utils/message_splitter.py`
- [ ] Implement `split_message()` with paragraph splitting
- [ ] Implement recursive splitting for oversized paragraphs
- [ ] Add HTML tag preservation logic
- [ ] Add code block detection and protection
- [ ] Implement `send_split_messages()` wrapper

### Phase 2: Testing
- [ ] Write unit tests for `split_message()`
- [ ] Test with various message lengths (1K, 5K, 10K, 20K chars)
- [ ] Test HTML tag preservation
- [ ] Test code block preservation
- [ ] Test recursive splitting edge cases
- [ ] Write integration tests for invoice formatter

### Phase 3: Integration
- [ ] Integrate into `InvoiceFormatterService`
- [ ] Integrate into `NotificationService.send_to_admins()`
- [ ] Integrate into `NotificationService.send_to_user()`
- [ ] Update all long-message callers to use wrapper
- [ ] Add safety assertions (message length <= 4096)

### Phase 4: Validation
- [ ] Manual test: 100-item cart checkout
- [ ] Manual test: 50-item order cancellation
- [ ] Manual test: Admin broadcast with long message
- [ ] Performance test: Measure split time for 20K char message
- [ ] Verify no regressions in existing flows

---

## Edge Cases to Handle

1. **Single paragraph > 4096 chars**
   → Split at sentence boundaries within paragraph

2. **Single sentence > 4096 chars**
   → Split at word boundaries (should be rare)

3. **Code block > 4096 chars**
   → Keep intact, add "[truncated, see attachment]" warning

4. **HTML tag at split boundary**
   → Close tag before split, reopen after (e.g., `</b>` → `<b>`)

5. **Empty split segments**
   → Filter out before sending

6. **Rate limiting**
   → Add configurable delay between message sends (default: 500ms)

---

## Performance Considerations

- **String splitting:** O(n) where n = message length
- **HTML parsing:** Use regex, not full HTML parser (fast)
- **Message sending:** Sequential (no parallelization needed)
- **Expected overhead:** < 10ms for 10K char message

---

## Future Enhancements (Out of Scope)

- Smart tier table splitting (keep tier header + price rows together)
- Telegram-native pagination buttons ("Previous", "Next")
- Message compression (remove redundant whitespace)
- Admin setting: Enable/disable splitting per notification type

---

## Success Criteria

- [ ] No message exceeds 4096 characters in production
- [ ] All inline buttons work correctly (attached to last message)
- [ ] No HTML formatting broken across splits
- [ ] No UX degradation compared to current single-message flow
- [ ] Comprehensive test coverage (>90%)
- [ ] Performance impact < 50ms for typical messages

---

## Related Issues

- Issue #22: Telegram Message Size Limit Risk (origin)
- Existing TODO: `2025-11-19_TODO_message-truncate-4096-chars.md` (may be duplicate)

---

## Notes

- Keep safety margin: Use 4000 char limit instead of 4096 to account for HTML tags
- Test with real data: Use production-sized carts for validation
- Monitor logs: Add warning when splitting occurs (for analytics)
- Document in CHANGELOG: Mention improved large cart UX
