import secrets
import string


def generate_code() -> str:
    """Generate a 6-digit verification code."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def generate_referral_code() -> str:
    """Generate an 8-char alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))
