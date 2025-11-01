# Admin ID Security - Design Decision

## Problem Statement

Original security audit Finding 2 suggested hashing admin IDs to prevent identification if `.env` file is compromised. However, this creates a functional conflict:

**Admin IDs are required for:**
- Sending notifications (new orders, errors, system events)
- Startup messages ("Bot is working")
- Admin-specific operations (order management, user bans)

**With hashed-only storage:**
- System cannot send notifications (doesn't know plaintext IDs)
- Breaks core functionality
- Not a viable solution

---

## Implemented Solution

**Hybrid Approach:**
1. **Store plaintext Admin IDs in `.env`** (required for notifications)
2. **Generate hashes at runtime** from plaintext IDs (for verification)
3. **Use hashes for permission checks** (defense-in-depth)

### How It Works

```python
# config.py - Computed hashes from plaintext IDs
ADMIN_ID_LIST = [123456789, 987654321]  # From .env
ADMIN_ID_HASHES = [generate_admin_id_hash(id) for id in ADMIN_ID_LIST]

# utils/custom_filters.py - Verification uses hashes
def __call__(self, message):
    return verify_admin_id(message.from_user.id, config.ADMIN_ID_HASHES)
```

### Security Benefits

1. **Defense-in-Depth:**
   - Admin checks use hashes (not direct ID comparison)
   - Adds computational layer for verification
   - Makes timing attacks more difficult

2. **Code Consistency:**
   - All admin checks use same verification function
   - Single source of truth for admin status
   - Easier to audit

3. **Future-Proofing:**
   - Can easily add TOTP/2FA to admin checks
   - Can implement admin session tokens
   - Can add admin activity logging

---

## Why Original Proposal Was Infeasible

**Original Proposal:**
```env
# Store only hashes
ADMIN_ID_HASHES=abc123...,def456...
```

**Problems:**
1. ❌ Cannot send "Bot is working" startup message
2. ❌ Cannot notify admins of new orders
3. ❌ Cannot send error notifications
4. ❌ Cannot send system alerts
5. ❌ Breaks admin notification system entirely

**Reality:** Telegram bots MUST know plaintext user IDs to send messages.

---

## Alternative Security Measures

Since we must store plaintext admin IDs, focus on protecting the `.env` file:

### 1. File System Permissions

```bash
chmod 600 .env          # Owner read/write only
chown botuser:botuser .env  # Owned by bot service user
```

### 2. Secrets Management (Production)

**Option A: HashiCorp Vault**
```python
import hvac
client = hvac.Client(url='https://vault:8200')
ADMIN_ID_LIST = client.secrets.kv.read_secret_version(path='bot/admin_ids')
```

**Option B: AWS Secrets Manager**
```python
import boto3
secrets = boto3.client('secretsmanager')
ADMIN_ID_LIST = secrets.get_secret_value(SecretId='bot/admin_ids')
```

**Option C: Environment Variables (Docker/K8s)**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bot-secrets
data:
  admin_ids: MTIzNDU2Nzg5LDk4NzY1NDMyMQ==  # Base64 encoded
```

### 3. Access Monitoring

```python
# Log all .env file access (audit trail)
import logging
logging.info(f"Config loaded by {os.getuid()} at {datetime.now()}")
```

### 4. Intrusion Detection

```bash
# Monitor .env file for unauthorized access (Linux)
auditctl -w /path/to/.env -p war -k env_access

# View audit log
ausearch -k env_access
```

### 5. Principle of Least Privilege

- Bot process runs as non-root user
- `.env` only readable by bot user
- No SSH access for bot user
- Separate deployment keys (read-only)

---

## Security Assessment

### Attack Scenarios

**Scenario 1: Attacker Reads .env File**
- **Impact:** Admin IDs exposed
- **Mitigation:**
  - File permissions prevent unauthorized read
  - OS-level access control
  - Audit logging detects access attempts
  - Secrets rotation policy

**Scenario 2: Attacker Gains Shell Access**
- **Impact:** Full system compromise (admin IDs are least concern)
- **Mitigation:**
  - Defense in depth (firewall, IDS, SELinux)
  - Regular security updates
  - Intrusion detection
  - Incident response plan

**Scenario 3: Application Vulnerability (RCE)**
- **Impact:** Attacker can read environment variables
- **Mitigation:**
  - Code review and security audits
  - Input validation
  - Dependency updates
  - WAF/rate limiting

### Risk Analysis

| Threat | Likelihood | Impact | Mitigation Effectiveness |
|--------|-----------|--------|-------------------------|
| Unauthorized .env read | LOW | MEDIUM | HIGH (file permissions) |
| Memory dump attack | VERY LOW | HIGH | MEDIUM (OS protections) |
| Social engineering | LOW | HIGH | HIGH (training, MFA) |
| Backup exposure | MEDIUM | MEDIUM | HIGH (encrypted backups) |

**Overall Risk Level:** LOW (with proper file permissions)

---

## Recommendations

1. ✅ **File Permissions** (chmod 600 .env) - CRITICAL
2. ✅ **Secrets Management** in production - HIGH
3. ✅ **Access Monitoring** (audit logs) - MEDIUM
4. ✅ **Regular Rotation** of admin IDs if compromise suspected - MEDIUM
5. ✅ **Encrypted Backups** - MEDIUM

---

## Comparison with Industry Practices

### Telegram Bot Libraries (Node.js, Python, Go)

**ALL require plaintext admin IDs for notifications.**

```javascript
// Telegraf (Node.js)
bot.telegram.sendMessage(ADMIN_ID, 'New order received')

// python-telegram-bot
bot.send_message(chat_id=ADMIN_ID, text='New order')

// gotgbot (Go)
bot.SendMessage(adminID, "New order", nil)
```

**Industry Standard:** Store admin IDs securely, protect access to config files.

### Comparison with Other Bots

| Bot/Service | Admin Storage | Notification Support |
|-------------|--------------|---------------------|
| AiogramShopBot | Plaintext IDs | ✅ Full support |
| Most Telegram bots | Plaintext IDs | ✅ Full support |
| Discord bots | User IDs | ✅ Full support |
| Slack bots | User IDs | ✅ Full support |

**Conclusion:** Plaintext user IDs for notifications are industry standard and unavoidable.

---

## Future Enhancements

1. **Admin Session Tokens** (short-lived JWT)
   - Admin logs in with ID + TOTP
   - Receives time-limited session token
   - Token stored in Redis (not .env)

2. **Webhook-Based Notifications**
   - Admins register webhook URLs
   - System sends HTTP POST instead of Telegram message
   - Decouples admin identity from Telegram IDs

3. **Multi-Factor Authentication**
   - Admin command requires TOTP code
   - Stored separately from Telegram ID
   - Time-based one-time passwords

4. **Admin Activity Audit Log**
   - Log all admin actions with timestamp
   - Detect suspicious patterns
   - Alert on unusual activity

---

## Conclusion

**Decision:** Store plaintext admin IDs in `.env` with strong file permissions.

**Rationale:**
- Functional requirement for notifications
- Industry standard approach
- Adequate security with proper file protections
- Pragmatic balance between security and functionality

**Rejected Alternative:** Hash-only storage (breaks core functionality)

**Security Posture:** ACCEPTABLE (with recommended mitigations in place)

---

**Last Updated:** 2025-11-01
**Status:** Final decision - implemented and documented
