import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.models import WaitlistUser
from app.services.email_queue import get_redis

logger = logging.getLogger(__name__)
router = Router()

_admin_bot: Bot | None = None


def set_admin_bot(bot: Bot):
    global _admin_bot
    _admin_bot = bot


async def notify_admin(text: str):
    """Send a notification to admin via admin bot. Silently skips if not configured."""
    if _admin_bot and settings.admin_telegram_id:
        try:
            await _admin_bot.send_message(settings.admin_telegram_id, text)
        except Exception as e:
            logger.error("Failed to notify admin: %s", e)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != settings.admin_telegram_id:
        return

    async with async_session() as session:
        total = (await session.execute(select(func.count(WaitlistUser.id)))).scalar()
        verified = (await session.execute(
            select(func.count(WaitlistUser.id)).where(WaitlistUser.status == "verified")
        )).scalar()
        pending = total - verified

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = (await session.execute(
            select(func.count(WaitlistUser.id)).where(WaitlistUser.created_at >= today_start)
        )).scalar()

        top_referrers = (await session.execute(
            select(WaitlistUser.email, WaitlistUser.referral_count)
            .where(WaitlistUser.referral_count > 0)
            .order_by(WaitlistUser.referral_count.desc())
            .limit(5)
        )).all()

    r = await get_redis()
    today_key = f"emails_sent:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    emails_today = int(await r.get(today_key) or 0)

    text = (
        f"Snake Battle Stats\n\n"
        f"Total signups: {total}\n"
        f"Verified: {verified}\n"
        f"Pending: {pending}\n\n"
        f"New today: {new_today}\n"
        f"Emails sent today: {emails_today}\n"
    )

    if top_referrers:
        text += "\nTop referrers:\n"
        for i, (email, count) in enumerate(top_referrers, 1):
            masked = email[:3] + "***" + email[email.index("@"):]
            text += f"{i}. {masked} — {count} refs\n"

    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    if message.from_user.id != settings.admin_telegram_id:
        return

    await message.answer(
        "Admin Bot Commands:\n\n"
        "/stats — Waitlist stats + top referrers\n"
        "/help — This message"
    )


def setup_admin_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
