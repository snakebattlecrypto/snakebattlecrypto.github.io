from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    resend_api_key: str
    from_email: str = "noreply@snakebattle.cc"
    admin_bot_token: str = ""
    admin_telegram_id: int = 0
    webhook_url: str
    frontend_url: str = "https://snakebattle.cc"
    db_password: str = ""
    redis_url: str = "redis://:snakebattle_redis@redis:6379/0"
    webhook_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
