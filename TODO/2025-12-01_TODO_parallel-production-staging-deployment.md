# TODO: Parallel Production and Staging Environment Setup

**Status:** Todo
**Priority:** Medium
**Created:** 2025-12-01
**Assignee:** DevOps Team

---

## Objective

Enable parallel operation of **Production** and **Staging** bot environments on a single server using Docker Compose with:
- Separate bot instances
- Separate databases
- Separate Redis instances
- Separate Caddy domains
- Isolated containers

---

## Use Case

- **Production:** Live bot for real users
- **Staging:** Demo/test environment for testing new features before production deployment

---

## Technical Requirements

### 1. Container Isolation
- Different container names
- Different internal ports
- Different Docker Compose project names
- Separate Docker networks (or shared `caddy` network with unique labels)

### 2. Port Allocation
- **Production:** Port 5000 (internal)
- **Staging:** Port 5001 (internal)
- Both exposed via Caddy reverse proxy on ports 80/443

### 3. Environment Configuration
- **Production:** `.env.prod`
- **Staging:** `.env.staging`
- Separate bot tokens (recommended) or same token (if supported by Telegram)
- Separate database files

### 4. Data Separation
- **Production DB:** `data/database.prod.db`
- **Staging DB:** `data/database.staging.db`
- **Production Backups:** `backups/prod/`
- **Staging Backups:** `backups/staging/`

### 5. Domain Configuration
- **Production:** `bot.yourdomain.com`
- **Staging:** `staging-bot.yourdomain.com` or `demo.yourdomain.com`

---

## Implementation Steps

### Step 1: Create Staging Docker Compose File

Create `docker-compose.staging.yml` based on `docker-compose.prod.yml`:

```yaml
# docker-compose.staging.yml
services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: shopbot-staging
    env_file:
      - .env.staging
    labels:
      caddy: https://staging-bot.yourdomain.com
      caddy.reverse_proxy: "{{upstreams 5001}}"
    depends_on:
      - redis
    networks:
      - caddy
      - shopbot_staging_network
    ports:
      - "5001:5001"
    expose:
      - 5001
    volumes:
      - ./data/staging:/bot/data
      - ./backups/staging:/bot/backups
    command: ["python", "-u", "run.py"]
    restart: always

  redis:
    image: redis:7-alpine
    container_name: shopbot-redis-staging
    command:
      - /bin/sh
      - -c
      - redis-server --requirepass "${REDIS_PASSWORD:?REDIS_PASSWORD variable is not set}"
    ports:
      - "6380:6379"  # Different external port to avoid conflict
    env_file:
      - .env.staging
    volumes:
      - redis_staging_data:/data
    restart: always
    networks:
      - shopbot_staging_network

volumes:
  redis_staging_data:
    driver: local

networks:
  shopbot_staging_network:
    driver: bridge
  caddy:
    external: true
```

### Step 2: Create Staging Environment File

Copy and modify `.env.prod.template` → `.env.staging`:

```bash
cp .env.prod.template .env.staging
```

**Key changes in `.env.staging`:**
```bash
# Use different bot token (or same if Telegram allows multiple webhooks)
TOKEN=<staging_bot_token>

# Different webapp port
WEBAPP_PORT=5001

# Different database
DB_NAME=database.staging.db

# Different Redis password
REDIS_PASSWORD=<different_password>

# Staging domain
WEBAPP_HOST=staging-bot.yourdomain.com

# Relaxed rate limits for testing
MAX_ORDERS_PER_USER_PER_HOUR=100

# Different Redis host (use localhost or container name)
REDIS_HOST=localhost

# Less strict backups for staging
DB_BACKUP_ENABLED=true
DB_BACKUP_INTERVAL_HOURS=24
DB_BACKUP_RETENTION_DAYS=3
```

### Step 3: Create Data Directories

```bash
mkdir -p data/staging
mkdir -p backups/staging
```

### Step 4: Start Both Environments

**Start Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Start Staging:**
```bash
docker-compose -f docker-compose.staging.yml up -d
```

### Step 5: Verify Both Running

```bash
# Check production
curl https://bot.yourdomain.com/health

# Check staging
curl https://staging-bot.yourdomain.com/health

# Check containers
docker ps | grep shopbot
```

Expected output:
```
shopbot-prod           Running
shopbot-redis-prod     Running
shopbot-staging        Running
shopbot-redis-staging  Running
```

---

## Advanced Configuration

### Option 1: Same Bot Token, Different Webhooks

If using the same bot token for both environments (not recommended):
- Telegram allows only ONE webhook per bot
- Solution: Use polling for staging instead of webhooks
- Modify staging config: Set `RUNTIME_ENVIRONMENT=POLLING` (requires code changes)

### Option 2: Separate Bot Tokens (Recommended)

- Create two bots via @BotFather
- Production bot: `@YourShopBot`
- Staging bot: `@YourShopBotStaging` or `@YourShopBotDev`
- Each has its own token and webhook

### Option 3: Docker Compose Projects

Use project names to avoid conflicts:

```bash
# Production
docker-compose -p shopbot-prod -f docker-compose.prod.yml up -d

# Staging
docker-compose -p shopbot-staging -f docker-compose.staging.yml up -d
```

---

## Caddy Configuration

External Caddy should already auto-discover both services via labels:

```caddyfile
# Automatically configured via Docker labels
https://bot.yourdomain.com {
    reverse_proxy shopbot-prod:5000
}

https://staging-bot.yourdomain.com {
    reverse_proxy shopbot-staging:5001
}
```

---

## Monitoring & Logs

**View production logs:**
```bash
docker-compose -f docker-compose.prod.yml logs -f bot
```

**View staging logs:**
```bash
docker-compose -f docker-compose.staging.yml logs -f bot
```

---

## Deployment Workflow

1. **Develop feature** in local dev environment
2. **Test feature** in staging environment
3. **Verify** with real users on staging bot
4. **Deploy to production** after approval

---

## Rollback Strategy

If production deployment fails:

```bash
# Stop production
docker-compose -f docker-compose.prod.yml down

# Restore previous backup
cp backups/prod/database_YYYY-MM-DD_HH-MM-SS.db data/database.prod.db

# Start production with previous code
git checkout <previous_commit>
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## Security Considerations

- **Separate admin access:** Use different ADMIN_ID_LIST for staging
- **Test data only:** Never use real user data in staging
- **Access control:** Consider restricting staging bot to specific user IDs
- **Backup separation:** Keep production and staging backups separate

---

## Cost Optimization

- **Staging:** Disable automated backups or reduce frequency
- **Staging:** Use smaller Redis memory limits
- **Staging:** Lower rate limits and resource allocation

---

## Future Enhancements

- [ ] Add CI/CD pipeline for automated staging deployments
- [ ] Implement blue-green deployment for zero-downtime updates
- [ ] Add health check monitoring for both environments
- [ ] Create admin dashboard to switch between production/staging

---

## References

- Docker Compose Documentation: https://docs.docker.com/compose/
- Caddy Docker Proxy: https://github.com/lucaslorentz/caddy-docker-proxy
- Multi-environment setups: https://12factor.net/config

---

## Notes

- This setup allows independent updates to staging without affecting production
- Both environments share the same Caddy reverse proxy
- Resource usage: ~2x memory and CPU compared to single environment
- Recommended: Minimum 2GB RAM for both environments
