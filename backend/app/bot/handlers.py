import logging
from datetime import datetime, timezone

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound

from app.database import async_session
from app.models import WaitlistUser
from app.services.email_queue import get_redis
from app.services.verification import generate_referral_code

logger = logging.getLogger(__name__)
router = Router()

MAX_CODE_ATTEMPTS = 10
ATTEMPT_WINDOW = 900  # 15 minutes


async def _check_rate_limit(telegram_id: int) -> bool:
    """Check brute-force rate limit via Redis. Works across all workers."""
    r = await get_redis()
    key = f"code_attempts:{telegram_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, ATTEMPT_WINDOW)
    return count <= MAX_CODE_ATTEMPTS


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to Snake Battle!\n\n"
        "Enter your 6-digit verification code from email to get started."
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(WaitlistUser).where(WaitlistUser.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer("You haven't verified yet. Enter your 6-digit code or visit snakebattle.cc")
        return

    position = user.waitlist_position or "N/A"
    await message.answer(
        f"Status: {user.status.upper()}\n"
        f"Position: #{position}\n"
        f"Referrals: {user.referral_count} people"
    )


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(WaitlistUser).where(WaitlistUser.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user or user.status != "verified":
        await message.answer("Verify first to get your referral link. Enter your 6-digit code.")
        return

    if not user.referral_code:
        await message.answer("Something went wrong with your referral code. Please contact support.")
        return

    await message.answer(
        f"Your referral link:\nsnakebattle.cc/?ref={user.referral_code}\n\n"
        f"You've invited {user.referral_count} people."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/start - Start verification\n"
        "/status - Your waitlist status\n"
        "/referral - Your referral link\n"
        "/help - Show this message"
    )


@router.message(F.text.regexp(r"^\d{6}$"))
async def handle_code(message: Message):
    code = message.text.strip()
    now = datetime.now(timezone.utc)
    telegram_id = message.from_user.id

    # Brute-force protection via Redis (shared across all workers)
    if not await _check_rate_limit(telegram_id):
        await message.answer("Too many attempts. Please wait 15 minutes and try again.")
        return

    async with async_session() as session:
        # Check if this telegram_id is already linked
        existing = await session.execute(
            select(WaitlistUser).where(WaitlistUser.telegram_id == telegram_id)
        )
        if existing.scalar_one_or_none():
            await message.answer("You are already verified!")
            return

        # Find user by code — lock row to prevent race conditions
        try:
            result = await session.execute(
                select(WaitlistUser)
                .where(
                    WaitlistUser.verification_code == code,
                    WaitlistUser.code_expires_at > now,
                    WaitlistUser.status == "pending",
                )
                .with_for_update()
            )
            user = result.scalar_one_or_none()
        except MultipleResultsFound:
            logger.warning("Code collision detected for code %s", code)
            await message.answer("Something went wrong. Please request a new code at snakebattle.cc")
            return

        if not user:
            logger.info("Failed code attempt from telegram_id=%d, code=%s", telegram_id, code)
            await message.answer("Invalid or expired code. Request a new one at snakebattle.cc")
            return

        # Generate unique referral code with collision retry
        ref_code = None
        for _ in range(5):
            candidate = generate_referral_code()
            exists = await session.execute(
                select(WaitlistUser.id).where(WaitlistUser.referral_code == candidate)
            )
            if not exists.scalar_one_or_none():
                ref_code = candidate
                break

        if not ref_code:
            logger.error("Failed to generate unique referral code after 5 attempts")
            await message.answer("Something went wrong. Please try again.")
            return

        # Verify user
        user.telegram_id = telegram_id
        user.status = "verified"
        user.referral_code = ref_code
        user.verification_code = None

        # Increment referrer's count (prevent self-referral by checking user IDs)
        if user.referred_by:
            referrer = await session.execute(
                select(WaitlistUser).where(WaitlistUser.referral_code == user.referred_by)
            )
            referrer_user = referrer.scalar_one_or_none()
            if referrer_user and referrer_user.id != user.id:
                await session.execute(
                    update(WaitlistUser)
                    .where(WaitlistUser.id == referrer_user.id)
                    .values(referral_count=WaitlistUser.referral_count + 1)
                )

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.warning("Verification conflict for code %s", code)
            await message.answer("Verification conflict. Please try again.")
            return

    await message.answer(
        f"Verified! Welcome to Snake Battle.\n\n"
        f"Your referral link:\nsnakebattle.cc/?ref={ref_code}\n\n"
        f"Share it to climb the waitlist!"
    )


@router.message()
async def handle_unknown(message: Message):
    await message.answer(
        "Send your 6-digit verification code, or use /help to see available commands."
    )


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
