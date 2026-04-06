import asyncio
import json
import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import WaitlistUser

logger = logging.getLogger(__name__)

QUEUE_KEY = "email_queue"
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


async def enqueue_email(to_email: str):
    """Push an email task onto the Redis queue. Code is fetched from DB at send time."""
    r = await get_redis()
    task = json.dumps({"to_email": to_email, "retries": 0})
    await r.lpush(QUEUE_KEY, task)
    logger.info("Enqueued verification email for %s", to_email)


async def _get_current_code(email: str) -> str | None:
    """Look up the current verification code from the database."""
    async with async_session() as session:
        result = await session.execute(
            select(WaitlistUser.verification_code).where(WaitlistUser.email == email)
        )
        return result.scalar_one_or_none()


async def email_worker():
    """Background worker that processes the email queue."""
    # Import here to avoid circular imports
    from app.services.email import send_verification_email

    logger.info("Email worker started")
    r = await get_redis()

    while True:
        try:
            result = await r.brpop(QUEUE_KEY, timeout=1)

            if result is None:
                continue

            _, raw_task = result
            task = json.loads(raw_task)
            to_email = task["to_email"]
            retries = task.get("retries", 0)

            # Fetch current code from DB (not from queue)
            code = await _get_current_code(to_email)
            if not code:
                logger.info("No active code for %s, skipping", to_email)
                continue

            success = await send_verification_email(to_email, code)

            if success:
                today_key = f"emails_sent:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                await r.incr(today_key)
                await r.expire(today_key, 172800)

            if not success and retries < MAX_RETRIES:
                delay = RETRY_DELAYS[retries]
                logger.warning(
                    "Email to %s failed, retry %d/%d in %ds",
                    to_email, retries + 1, MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
                task["retries"] = retries + 1
                await r.lpush(QUEUE_KEY, json.dumps(task))
            elif not success:
                logger.error(
                    "Email to %s failed after %d retries, dropping",
                    to_email, MAX_RETRIES,
                )

        except asyncio.CancelledError:
            logger.info("Email worker stopped")
            break
        except Exception:
            logger.exception("Email worker error")
            await asyncio.sleep(1)
