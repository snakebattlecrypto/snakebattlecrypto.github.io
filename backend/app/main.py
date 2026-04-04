import asyncio
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.bot.handlers import setup_dispatcher
from app.config import settings
from app.database import engine
from app.models import Base
from app.routes.waitlist import limiter
from app.routes.waitlist import router as waitlist_router
from app.services.email_queue import close_redis, email_worker

bot = Bot(token=settings.telegram_bot_token)
dp = setup_dispatcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables, set webhook, start email worker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await bot.set_webhook(settings.webhook_url, drop_pending_updates=True)

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
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
