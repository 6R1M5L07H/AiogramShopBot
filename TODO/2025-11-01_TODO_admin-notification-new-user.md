# Admin Notification for New User Registration

**Priority:** Low
**Status:** TODO
**Estimated Effort:** Small (1-2 hours)

## Description

Add configurable admin notification when a new user registers (first /start command).

## Requirements

- Send notification to all admins when new user registers
- Include user information: username, Telegram ID, registration timestamp
- Make notification configurable via environment variable (enable/disable)
- Default: disabled (to avoid spam in high-traffic bots)

## Implementation Plan

### 1. Configuration
- [ ] Add `NOTIFY_ADMIN_NEW_USER` to .env.template (default: "false")
- [ ] Add config variable in config.py

### 2. Localization
- [ ] Add DE string: `admin_new_user_notification`
- [ ] Add EN string: `admin_new_user_notification`
- [ ] Format: User info, registration time, profile link

### 3. Service Layer
- [ ] Add method to NotificationService: `notify_new_user_registration()`
- [ ] Check config flag before sending
- [ ] Include user details and registration timestamp

### 4. Handler Integration
- [ ] Modify `start()` handler in run.py
- [ ] Call notification after user creation (only for NEW users, not existing)
- [ ] Ensure notification only sent once per user

### 5. Testing
- [ ] Test with NOTIFY_ADMIN_NEW_USER=true
- [ ] Test with NOTIFY_ADMIN_NEW_USER=false
- [ ] Verify notification only sent for new users (not on every /start)
- [ ] Test notification format and content

## Technical Notes

- Hook into `UserService.create_if_not_exist()` return value
- Only notify if user was actually created (not just loaded)
- Similar pattern to `admin_user_banned_notification`

## Message Format Example

```
👤 Neuer Benutzer registriert

Benutzer: @username (ID: 123456789)
Registriert: 2025-11-01 14:35

Profil: https://t.me/username
```

## Configuration Example

```env
# Admin Notifications
NOTIFY_ADMIN_NEW_USER=false  # Notify admins when new user registers
```
