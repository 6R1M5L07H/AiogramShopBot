import logging
import traceback

from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BufferedInputFile
from redis.asyncio import Redis
import config

# Validate critical configuration before bot initialization
from utils.config_validator import validate_or_exit
validate_or_exit(config)

# Initialize webhook configuration (must happen before app setup)
# This performs side effects (ngrok start, HTTP request) that were previously
# happening at module import time, which violated "import should be safe" principle
config.initialize_webhook_config()
logging.info(f"[Init] Webhook configuration initialized: {config.WEBHOOK_URL}")

# Load shipping types configuration for selected country
from utils.shipping_types_loader import load_shipping_types
try:
    _SHIPPING_TYPES = load_shipping_types(config.SHIPPING_COUNTRY)
    logging.info(f"[Init] Loaded shipping types for country: {config.SHIPPING_COUNTRY}")
except FileNotFoundError as e:
    logging.error(f"[Init] ❌ {e}")
    logging.error(f"[Init] ❌ Bot cannot start without shipping types configuration")
    exit(1)
except Exception as e:
    logging.error(f"[Init] ❌ Failed to load shipping types: {e}")
    exit(1)


def get_shipping_types() -> dict:
    """
    Get loaded shipping types configuration.

    Returns:
        dict: Shipping types for configured country

    Example:
        from bot import get_shipping_types
        shipping_types = get_shipping_types()
        maxibrief = shipping_types["maxibrief"]
    """
    return _SHIPPING_TYPES

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request, status, HTTPException
from contextlib import asynccontextmanager
from db import create_db_and_tables
import uvicorn
from fastapi.responses import JSONResponse
from processing.processing import processing_router
from web.mini_app_router import mini_app_router
from web.api_router import api_router
from services.notification import NotificationService
from jobs.payment_timeout_job import PaymentTimeoutJob
from jobs.database_backup_job import backup_scheduler
from jobs.data_retention_cleanup_job import start_data_retention_cleanup_job
from middleware.security_headers import SecurityHeadersMiddleware, CSPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import asyncio

redis = Redis(host=config.REDIS_HOST, password=config.REDIS_PASSWORD)
bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=RedisStorage(redis))

# Background tasks
backup_task = None
data_retention_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global backup_task, data_retention_task

    # Startup
    await create_db_and_tables()
    await bot.set_webhook(
        url=config.WEBHOOK_URL,
        secret_token=config.WEBHOOK_SECRET_TOKEN
    )
    logging.info(f"[Startup] Webhook registered with Telegram")

    # Start payment timeout job
    await payment_timeout_job.start()

    # Start database backup scheduler (if enabled)
    if config.DB_BACKUP_ENABLED:
        backup_task = asyncio.create_task(backup_scheduler())
        logging.info("[Startup] Database backup scheduler started")
    else:
        logging.info("[Startup] Database backup scheduler disabled")

    # Start data retention cleanup job (always enabled for data minimization)
    data_retention_task = asyncio.create_task(start_data_retention_cleanup_job())
    logging.info("[Startup] Data retention cleanup job started")

    # Notify admins on startup
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, 'Bot is working')
        except Exception as e:
            logging.warning(e)

    yield

    # Shutdown
    logging.warning('Shutting down..')

    # Stop payment timeout job
    await payment_timeout_job.stop()

    # Stop database backup scheduler
    if backup_task is not None:
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            logging.info("[Shutdown] Database backup scheduler stopped")

    # Stop data retention cleanup job
    if data_retention_task is not None:
        data_retention_task.cancel()
        try:
            await data_retention_task
        except asyncio.CancelledError:
            logging.info("[Shutdown] Data retention cleanup job stopped")

    await bot.delete_webhook()
    await dp.storage.close()
    logging.warning('Bye!')


app = FastAPI(lifespan=lifespan)

# Add security middleware (disabled by default for API-only bots)
# Enable when adding web-based UI (admin dashboard, status pages, etc.)
if config.WEBHOOK_SECURITY_HEADERS_ENABLED:
    app.add_middleware(SecurityHeadersMiddleware)
    logging.info("[Startup] Security headers middleware enabled")
else:
    logging.debug("[Startup] Security headers middleware disabled (not needed for API-only bot)")

if config.WEBHOOK_CSP_ENABLED:
    app.add_middleware(CSPMiddleware)
    logging.info("[Startup] Content Security Policy middleware enabled")
else:
    logging.debug("[Startup] CSP middleware disabled (not needed for API-only bot)")

if config.WEBHOOK_CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.WEBHOOK_CORS_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["POST"],  # Only allow POST for webhooks
        allow_headers=["Content-Type", "X-Telegram-Bot-Api-Secret-Token", "X-Telegram-Init-Data"],
    )
    logging.info(f"[Startup] CORS middleware enabled for origins: {config.WEBHOOK_CORS_ALLOWED_ORIGINS}")
else:
    logging.debug("[Startup] CORS middleware disabled (no allowed origins configured)")

app.include_router(processing_router)
app.include_router(mini_app_router)
app.include_router(api_router)


# Health check endpoint (for Docker container monitoring)
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker healthcheck."""
    return {"status": "healthy"}


# Initialize payment timeout job
payment_timeout_job = PaymentTimeoutJob(check_interval_seconds=60)


@app.post(config.WEBHOOK_PATH)
async def webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

    # Security: Reject requests without secret token header
    if secret_token is None:
        logging.warning("Webhook request rejected: Missing X-Telegram-Bot-Api-Secret-Token header")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Security: Use timing-safe comparison to prevent timing attacks
    import secrets
    if not secrets.compare_digest(secret_token, config.WEBHOOK_SECRET_TOKEN):
        logging.warning("Webhook request rejected: Invalid secret token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        update_data = await request.json()
        # Security: Do not log update_data - contains PII (messages, addresses, etc.)
        await dp.feed_webhook_update(bot, update_data)
        logging.info(f"✅ Webhook processed successfully")
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"status": "error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {exc}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    await NotificationService.send_to_admins(admin_notification, None)
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred: {str(exc)}"},
    )


def main() -> None:
    uvicorn.run(app, host=config.WEBAPP_HOST, port=config.WEBAPP_PORT)
