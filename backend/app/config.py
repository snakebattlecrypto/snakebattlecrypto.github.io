from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "eu-north-1"
    ses_from_email: str = "noreply@snakebattle.cc"
    webhook_url: str
    frontend_url: str = "https://snakebattle.cc"
    db_password: str = ""
    redis_url: str = "redis://redis:6379/0"
    webhook_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
