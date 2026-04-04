from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
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
    ref: str | None = None


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
        # Waitlist position = next available
        count_result = await session.execute(
            select(WaitlistUser.id).order_by(WaitlistUser.id.desc()).limit(1)
        )
        last = count_result.scalar_one_or_none()
        position = (last or 0) + 1

        user = WaitlistUser(
            email=email,
            waitlist_position=position,
            code_requests_count=1,
            code_requests_reset_at=now + timedelta(hours=1),
        )
        if body.ref:
            user.referred_by = body.ref
        session.add(user)

    # Generate new code (invalidates old one)
    code = generate_code()
    user.verification_code = code
    user.code_expires_at = now + timedelta(minutes=15)

    await session.commit()

    # Enqueue email for async delivery
    await enqueue_email(email, code)

    return WaitlistResponse(success=True, message="Verification code sent to your email")
