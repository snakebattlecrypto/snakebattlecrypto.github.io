import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.bot.admin import set_admin_bot, setup_admin_dispatcher
from app.bot.handlers import setup_dispatcher
from app.config import settings
from app.database import engine
from app.models import Base
from app.routes.waitlist import limiter
from app.routes.waitlist import router as waitlist_router
from app.services.email_queue import close_redis, email_worker

bot = Bot(token=settings.telegram_bot_token)
dp = setup_dispatcher()

# Generate webhook secret from bot token (deterministic, no extra env var needed)
WEBHOOK_SECRET = settings.webhook_secret or hashlib.sha256(
    settings.telegram_bot_token.encode()
).hexdigest()[:64]

# Admin bot (optional — only starts if ADMIN_BOT_TOKEN is set)
admin_bot: Bot | None = None
admin_dp: Dispatcher | None = None
ADMIN_WEBHOOK_SECRET: str | None = None

if settings.admin_bot_token:
    admin_bot = Bot(token=settings.admin_bot_token)
    admin_dp = setup_admin_dispatcher()
    set_admin_bot(admin_bot)
    ADMIN_WEBHOOK_SECRET = hashlib.sha256(
        settings.admin_bot_token.encode()
    ).hexdigest()[:64]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables, set webhook, start email worker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    for attempt in range(3):
        try:
            await bot.set_webhook(
                settings.webhook_url,
                drop_pending_updates=True,
                secret_token=WEBHOOK_SECRET,
            )
            break
        except TelegramRetryAfter as e:
            logging.warning("Webhook rate limited, retrying in %ds...", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
        except Exception as e:
            logging.warning("Webhook setup failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2)

    # Admin bot webhook
    if admin_bot:
        admin_webhook_url = settings.webhook_url.replace(
            "/api/telegram/webhook", "/api/admin/webhook"
        )
        for attempt in range(3):
            try:
                await admin_bot.set_webhook(
                    admin_webhook_url,
                    drop_pending_updates=True,
                    secret_token=ADMIN_WEBHOOK_SECRET,
                )
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                logging.warning("Admin webhook setup failed (attempt %d): %s", attempt + 1, e)
                await asyncio.sleep(2)

    worker_task = asyncio.create_task(email_worker())

    yield

    # Shutdown: stop worker, cleanup
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    await close_redis()
    await bot.delete_webhook()
    await bot.session.close()
    if admin_bot:
        await admin_bot.delete_webhook()
        await admin_bot.session.close()
    await engine.dispose()


app = FastAPI(title="Snake Battle API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        settings.frontend_url.replace("https://", "http://"),
        "http://localhost:8080",
    ],
    allow_methods=["POST"],
    allow_headers=["*"],
)

app.include_router(waitlist_router)


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    # Verify webhook secret from Telegram
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if token != WEBHOOK_SECRET:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.post("/api/admin/webhook")
async def admin_webhook(request: Request):
    if not admin_bot or not admin_dp:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if token != ADMIN_WEBHOOK_SECRET:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    data = await request.json()
    update = Update.model_validate(data, context={"bot": admin_bot})
    await admin_dp.feed_update(admin_bot, update)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
