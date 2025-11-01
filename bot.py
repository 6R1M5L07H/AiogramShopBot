import logging
import traceback

from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BufferedInputFile
from redis.asyncio import Redis
import config
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request, status, HTTPException
from db import create_db_and_tables
import uvicorn
from fastapi.responses import JSONResponse
from processing.processing import processing_router
from services.notification import NotificationService
from jobs.payment_timeout_job import PaymentTimeoutJob
from jobs.database_backup_job import backup_scheduler
from middleware.security_headers import SecurityHeadersMiddleware, CSPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import asyncio

redis = Redis(host=config.REDIS_HOST, password=config.REDIS_PASSWORD)
bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=RedisStorage(redis))
app = FastAPI()

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
        allow_headers=["Content-Type", "X-Telegram-Bot-Api-Secret-Token"],
    )
    logging.info(f"[Startup] CORS middleware enabled for origins: {config.WEBHOOK_CORS_ALLOWED_ORIGINS}")
else:
    logging.debug("[Startup] CORS middleware disabled (no allowed origins configured)")

app.include_router(processing_router)

# Initialize payment timeout job
payment_timeout_job = PaymentTimeoutJob(check_interval_seconds=60)

# Background task for database backups
backup_task = None


@app.post(config.WEBHOOK_PATH)
async def webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != config.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        update_data = await request.json()
        await dp.feed_webhook_update(bot, update_data)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"status": "error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


@app.on_event("startup")
async def on_startup():
    global backup_task

    await create_db_and_tables()
    await bot.set_webhook(
        url=config.WEBHOOK_URL,
        secret_token=config.WEBHOOK_SECRET_TOKEN
    )

    # Start payment timeout job
    await payment_timeout_job.start()

    # Start database backup scheduler (if enabled)
    if config.DB_BACKUP_ENABLED:
        backup_task = asyncio.create_task(backup_scheduler())
        logging.info("[Startup] Database backup scheduler started")
    else:
        logging.info("[Startup] Database backup scheduler disabled")

    # Notify admins on startup
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, 'Bot is working')
        except Exception as e:
            logging.warning(e)


@app.on_event("shutdown")
async def on_shutdown():
    global backup_task

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

    await bot.delete_webhook()
    await dp.storage.close()
    logging.warning('Bye!')


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
