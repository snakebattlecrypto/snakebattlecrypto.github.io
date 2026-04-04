from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.bot.handlers import setup_dispatcher
from app.config import settings
from app.database import engine
from app.models import Base
from app.routes.waitlist import router as waitlist_router

bot = Bot(token=settings.telegram_bot_token)
dp = setup_dispatcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables, set webhook
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await bot.set_webhook(settings.webhook_url, drop_pending_updates=True)
    yield
    # Shutdown
    await bot.delete_webhook()
    await bot.session.close()
    await engine.dispose()


app = FastAPI(title="Snake Battle API", lifespan=lifespan)

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
