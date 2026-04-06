import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_verification_email(to_email: str, code: str) -> bool:
    """Send a verification code email via Resend API."""
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;
                background: #0a0a0f; color: #ffffff; padding: 40px; border-radius: 16px;">
        <h1 style="text-align: center; font-size: 24px; margin-bottom: 8px;">
            <span style="color: #00d4ff;">SNAKE</span>
            <span style="color: #e040fb;">BATTLE</span>
        </h1>
        <p style="text-align: center; color: #999; font-size: 14px; margin-bottom: 32px;">
            Multiplayer PvP with Real Crypto Stakes
        </p>
        <p style="text-align: center; color: #ccc; font-size: 16px;">
            Your verification code:
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px;
                         color: #00d4ff; background: rgba(0,212,255,0.1);
                         padding: 16px 32px; border-radius: 12px; border: 1px solid rgba(0,212,255,0.3);">
                {code}
            </span>
        </div>
        <p style="text-align: center; color: #999; font-size: 13px;">
            Enter this code in our Telegram bot to verify.<br>
            Code expires in 15 minutes.
        </p>
    </div>
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.from_email,
                    "to": [to_email],
                    "subject": "Your Snake Battle verification code",
                    "html": html_body,
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                return True
            logger.error("Resend API error for %s: %s %s", to_email, response.status_code, response.text)
            return False
    except httpx.HTTPError as e:
        logger.error("Resend request failed for %s: %s", to_email, e)
        return False
