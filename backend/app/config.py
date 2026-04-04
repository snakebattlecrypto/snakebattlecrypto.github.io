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

    class Config:
        env_file = ".env"


settings = Settings()
