# GPG Public Key Display

**Date:** 2025-10-19
**Priority:** Low
**Estimated Effort:** Low (30 minutes)

---

## Description
Display the shop administrator's public GPG key in the main menu to enable users to verify encrypted communications and understand encryption options for sensitive data like shipping addresses.

## User Story
As a privacy-conscious customer, I want to see the shop's public GPG key, so that I can verify the identity of the shop and optionally encrypt sensitive information before sending it.

## Acceptance Criteria
- [ ] Main menu has "🔐 GPG Public Key" button (currently only in Cart)
- [x] Clicking button shows formatted public key in message
- [x] Message includes:
  - Full ASCII-armored public key block
  - Key fingerprint
  - Key expiration date (if applicable)
  - Short explanation of what GPG is
  - Link to GPG tutorial (optional)
- [x] "Copy Key" functionality (user can select and copy)
- [x] Back button to return to menu
- [x] Localization (DE/EN)

## Technical Notes

### Configuration (.env)
```bash
GPG_PUBLIC_KEY_FILE=/path/to/pubkey.asc
GPG_KEY_FINGERPRINT=ABCD1234EFGH5678...
```

### Implementation
Simple handler that reads public key file and displays it as monospace text with fingerprint and instructions.

## Current Status (2025-11-29)

**Partially Implemented** - Feature exists in Cart view, needs main menu placement.

**Completed:**
- [x] GPG configuration in `.env` and `config.py` (PGP_PUBLIC_KEY_BASE64)
- [x] Handler implemented in `handlers/user/cart.py:307` (Level 10)
- [x] Service method: `CartService.get_gpg_info_view()`
- [x] Localization keys added
- [x] Shows: End-to-end encryption, dual-layer security, public key, fingerprint

**Remaining Work:**
1. Add "🔐 GPG Public Key" button to main user menu
2. Create new handler or reuse existing `show_gpg_info()` from cart
3. Test main menu placement

## Dependencies
- Requires GPG public key file
- No database changes needed

---

**Status:** Partially Implemented - Feature exists in Cart, needs main menu placement