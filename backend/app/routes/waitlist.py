from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import get_session
from app.models import WaitlistUser
from app.services.email_queue import enqueue_email
from app.services.verification import generate_code

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)

MAX_CODES_PER_HOUR = 5


class WaitlistRequest(BaseModel):
    email: EmailStr
    ref: str | None = Field(None, max_length=8)


class WaitlistResponse(BaseModel):
    success: bool
    message: str


@router.post("/waitlist", response_model=WaitlistResponse)
@limiter.limit("10/minute")
async def join_waitlist(request: Request, body: WaitlistRequest, session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    email = body.email.lower().strip()

    # Find or create user
    result = await session.execute(select(WaitlistUser).where(WaitlistUser.email == email))
    user = result.scalar_one_or_none()

    if user and user.status == "verified":
        raise HTTPException(status_code=409, detail="Email already verified")

    # Validate referral code exists if provided
    valid_ref = None
    if body.ref:
        ref_exists = await session.execute(
            select(WaitlistUser.referral_code).where(WaitlistUser.referral_code == body.ref)
        )
        if ref_exists.scalar_one_or_none():
            valid_ref = body.ref

    if user:
        # Check rate limit
        if user.code_requests_reset_at and now < user.code_requests_reset_at:
            if user.code_requests_count >= MAX_CODES_PER_HOUR:
                raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
        else:
            user.code_requests_count = 0
            user.code_requests_reset_at = now + timedelta(hours=1)

        user.code_requests_count += 1
    else:
        # Atomic position assignment with advisory lock to prevent duplicates
        from sqlalchemy import func, text
        await session.execute(text("SELECT pg_advisory_xact_lock(1)"))
        pos_result = await session.execute(
            select(func.coalesce(func.max(WaitlistUser.waitlist_position), 0) + 1)
        )
        position = pos_result.scalar()

        user = WaitlistUser(
            email=email,
            waitlist_position=position,
            code_requests_count=1,
            code_requests_reset_at=now + timedelta(hours=1),
        )
        if valid_ref:
            user.referred_by = valid_ref
        session.add(user)

    # Generate new code (invalidates old one)
    code = generate_code()
    user.verification_code = code
    user.code_expires_at = now + timedelta(minutes=15)

    await session.commit()

    # Enqueue email for async delivery
    try:
        await enqueue_email(email)
    except Exception:
        # Redis down — fall back to direct send
        import logging
        logging.getLogger(__name__).warning("Redis enqueue failed for %s, sending directly", email)
        from app.services.email import send_verification_email
        await send_verification_email(email, code)

    return WaitlistResponse(success=True, message="Verification code sent to your email")
