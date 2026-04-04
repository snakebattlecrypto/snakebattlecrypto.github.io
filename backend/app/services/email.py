import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _get_ses_client():
    return boto3.client(
        "ses",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


async def send_verification_email(to_email: str, code: str) -> bool:
    """Send a verification code email via AWS SES. Returns True on success."""
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
        client = _get_ses_client()
        client.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Your Snake Battle verification code", "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        return True
    except ClientError:
        return False
