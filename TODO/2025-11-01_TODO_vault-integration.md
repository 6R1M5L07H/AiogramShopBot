# HashiCorp Vault Integration for Secrets Management

**Date:** 2025-11-01
**Priority:** Medium
**Status:** Planning
**Estimated Effort:** 4-6 hours
**Branch:** `feature/vault-secrets-management` (separate branch)

---

## Overview

Implement HashiCorp Vault as secure alternative to `.env` files for secrets management.

**Current State:**
- Secrets stored in plaintext `.env` file
- File permissions protect access
- Manual secret rotation
- No audit trail

**Desired State:**
- Encrypted secrets in Vault
- Centralized secrets management
- Audit logging
- Secret rotation support
- Optional: No plaintext files on disk

---

## Benefits

### Security
- ✅ Encrypted secrets at rest
- ✅ Audit logging (who accessed what, when)
- ✅ Access control policies
- ✅ Secret rotation support
- ✅ No accidental git commits

### Operations
- ✅ Centralized management
- ✅ Easy secret updates
- ✅ Multi-environment support (dev/staging/prod)
- ✅ Secrets versioning

### Development
- ✅ No email/registration required (self-hosted)
- ✅ Runs locally in Docker
- ✅ Vault UI for easy management
- ✅ Automatic fallback to .env

---

## Implementation Plan

### Phase 1: Docker Setup (1 hour)

**File:** `docker-compose.vault.yml`
```yaml
version: '3.8'

services:
  vault:
    image: vault:latest
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: dev-only-token
    cap_add:
      - IPC_LOCK
    volumes:
      - vault-data:/vault/file
    command: server -dev

  vault-ui:
    image: djenriquez/vault-ui:latest
    ports:
      - "8000:8000"
    environment:
      VAULT_URL_DEFAULT: http://vault:8200

volumes:
  vault-data:
```

**Tasks:**
- [ ] Create docker-compose.vault.yml
- [ ] Test Vault startup
- [ ] Verify Vault UI access (http://localhost:8000)
- [ ] Test basic secret operations

---

### Phase 2: Python Integration (2 hours)

**File:** `utils/vault_config.py`

**Features:**
- VaultConfig class for secret management
- get_all_secrets() - Load all secrets
- get_secret(key) - Get single secret
- set_secret(key, value) - Store secret
- Automatic fallback to .env if Vault unavailable

**Dependencies:**
```bash
pip install hvac
```

**Tasks:**
- [ ] Create VaultConfig class
- [ ] Implement get_all_secrets()
- [ ] Implement get_secret() with fallback
- [ ] Implement set_secret()
- [ ] Add error handling and logging
- [ ] Write unit tests

---

### Phase 3: Migration Tool (1.5 hours)

**File:** `utils/vault_migrate.py`

**Features:**
- Read secrets from .env
- Store in Vault
- Create .env backup
- Verify migration
- Interactive CLI

**Tasks:**
- [ ] Create migration script
- [ ] Add backup functionality
- [ ] Implement verification
- [ ] Add interactive prompts
- [ ] Test migration process

---

### Phase 4: config.py Integration (0.5 hours)

**Changes to `config.py`:**
```python
from utils.vault_config import VaultConfig

# Enable Vault (optional)
USE_VAULT = os.environ.get('USE_VAULT', 'false') == 'true'

if USE_VAULT:
    secrets = VaultConfig.get_all_secrets()
    TOKEN = secrets.get('TOKEN')
    ADMIN_ID_LIST = secrets.get('ADMIN_ID_LIST', '').split(',')
    # ... other secrets
else:
    # Fallback to .env (current behavior)
    TOKEN = os.environ.get('TOKEN')
    ADMIN_ID_LIST = os.environ.get('ADMIN_ID_LIST').split(',')
```

**Tasks:**
- [ ] Add VaultConfig import
- [ ] Add USE_VAULT flag
- [ ] Implement Vault secret loading
- [ ] Keep .env fallback
- [ ] Test both modes

---

### Phase 5: Documentation (1 hour)

**File:** `docs/VAULT_SETUP_GUIDE.md`

**Sections:**
1. Why Vault?
2. Quick Start (5 minutes)
3. Detailed Setup
4. Migration Process
5. Usage Examples
6. Vault UI Guide
7. Troubleshooting
8. Security Best Practices
9. Production Setup

**Tasks:**
- [ ] Write comprehensive guide
- [ ] Add screenshots of Vault UI
- [ ] Create troubleshooting section
- [ ] Document production setup
- [ ] Add CLI command reference

---

## Configuration

### Development Mode

**docker-compose.vault.yml:**
- Vault in dev mode (no persistence)
- Root token: `dev-only-token`
- No TLS (HTTP only)

**Environment Variables:**
```env
USE_VAULT=true
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=dev-only-token
VAULT_MOUNT_POINT=secret
VAULT_SECRET_PATH=aiogram-shop
```

### Production Mode

**Requirements:**
- Vault in production mode
- TLS enabled (HTTPS)
- Proper authentication (AppRole/K8s)
- Persistent storage
- Backup strategy
- Seal/unseal process

---

## Testing Checklist

### Manual Tests
- [ ] Start Vault container
- [ ] Access Vault UI
- [ ] Store secret via CLI
- [ ] Retrieve secret via Python
- [ ] Run migration tool
- [ ] Start bot with Vault enabled
- [ ] Verify fallback to .env works
- [ ] Test with Vault stopped (fallback)

### Integration Tests
- [ ] VaultConfig.get_secret() returns correct value
- [ ] Fallback to .env when Vault unavailable
- [ ] Migration creates backup
- [ ] Secrets match between .env and Vault

---

## Security Considerations

### Development
- ✅ Vault runs locally only
- ✅ No external network access
- ✅ Dev token acceptable (local only)

### Production
- ⚠️ **NEVER** use dev mode
- ✅ Enable TLS (HTTPS)
- ✅ Use AppRole authentication
- ✅ Enable audit logging
- ✅ Regular backups
- ✅ Seal Vault when not in use
- ✅ Rotate tokens regularly

---

## Alternative Solutions

### Option 1: Doppler (Cloud-based)
**Pros:**
- Easy setup
- Free tier available
- Good UI

**Cons:**
- Requires email registration
- Cloud-based (not local)
- Vendor lock-in

### Option 2: Docker Secrets
**Pros:**
- Docker-native
- No additional software
- Simple

**Cons:**
- No UI
- No audit logging
- Limited features

### Option 3: SOPS (Mozilla)
**Pros:**
- File-based
- Git-friendly
- No external services

**Cons:**
- No UI
- Manual key management
- Requires GPG/age

**Decision:** HashiCorp Vault (best balance of features, security, and local deployment)

---

## Implementation Notes

### File Structure
```
.
├── docker-compose.vault.yml         # Vault containers
├── utils/
│   ├── vault_config.py              # VaultConfig class
│   └── vault_migrate.py             # Migration tool
├── docs/
│   └── VAULT_SETUP_GUIDE.md         # Setup guide
└── .env
    USE_VAULT=true                   # Enable Vault
    VAULT_ADDR=http://localhost:8200
    VAULT_TOKEN=dev-only-token
```

### Migration Path
1. User runs: `docker-compose -f docker-compose.vault.yml up -d`
2. User runs: `python -m utils.vault_migrate`
3. Tool creates `.env.backup.TIMESTAMP`
4. Tool stores secrets in Vault
5. User updates `.env`: `USE_VAULT=true`
6. Bot loads secrets from Vault
7. User keeps `.env.backup` in safe place

---

## Success Criteria

- [ ] Vault runs in Docker
- [ ] Secrets migrate from .env successfully
- [ ] Bot starts with Vault-loaded secrets
- [ ] Fallback to .env works when Vault unavailable
- [ ] Documentation is complete and clear
- [ ] All tests pass

---

## Dependencies

### Python Packages
```bash
pip install hvac  # HashiCorp Vault client
```

### Docker Images
- `vault:latest` (~200MB)
- `djenriquez/vault-ui:latest` (~50MB)

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Docker Setup | 1 hour | Vault running locally |
| 2. Python Integration | 2 hours | VaultConfig class |
| 3. Migration Tool | 1.5 hours | vault_migrate.py |
| 4. config.py Integration | 0.5 hours | Vault-enabled config |
| 5. Documentation | 1 hour | VAULT_SETUP_GUIDE.md |
| **Total** | **6 hours** | Full Vault integration |

---

## Related TODOs

- Finding 2: Admin ID Security (could use Vault for storage)
- Finding 5: Database Backup System (Vault can backup secrets)

---

## References

- [HashiCorp Vault Docs](https://www.vaultproject.io/docs)
- [hvac Python Client](https://hvac.readthedocs.io/)
- [Vault Docker Hub](https://hub.docker.com/_/vault)
- [Vault UI](https://github.com/djenriquez/vault-ui)

---

## Notes

- Implementation should be in **separate branch**: `feature/vault-secrets-management`
- Keep .env fallback for backward compatibility
- Test thoroughly before merging to develop
- Consider making Vault optional (USE_VAULT=false by default)
- Production setup requires additional hardening

---

**Status:** Ready for Implementation
**Next Step:** Create branch and start with Phase 1 (Docker Setup)
