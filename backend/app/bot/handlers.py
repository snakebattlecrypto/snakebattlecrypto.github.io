from datetime import datetime, timezone

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, update

from app.database import async_session
from app.models import WaitlistUser
from app.services.verification import generate_referral_code

router = Router()


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

    await message.answer(
        f"Status: {user.status.upper()}\n"
        f"Position: #{user.waitlist_position}\n"
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

    async with async_session() as session:
        # Check if this telegram_id is already linked
        existing = await session.execute(
            select(WaitlistUser).where(WaitlistUser.telegram_id == message.from_user.id)
        )
        if existing.scalar_one_or_none():
            await message.answer("You are already verified!")
            return

        # Find user by code
        result = await session.execute(
            select(WaitlistUser).where(
                WaitlistUser.verification_code == code,
                WaitlistUser.code_expires_at > now,
                WaitlistUser.status == "pending",
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Invalid or expired code. Request a new one at snakebattle.cc")
            return

        # Verify user
        ref_code = generate_referral_code()
        user.telegram_id = message.from_user.id
        user.status = "verified"
        user.referral_code = ref_code
        user.verification_code = None

        # Increment referrer's count
        if user.referred_by:
            await session.execute(
                update(WaitlistUser)
                .where(WaitlistUser.referral_code == user.referred_by)
                .values(referral_count=WaitlistUser.referral_count + 1)
            )

        await session.commit()

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
