from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WaitlistUser(Base):
    __tablename__ = "waitlist_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    verification_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    code_requests_count: Mapped[int] = mapped_column(Integer, default=0)
    code_requests_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(8), unique=True, nullable=True)
    referred_by: Mapped[str | None] = mapped_column(String(8), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    waitlist_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_verification_lookup", "verification_code", "code_expires_at"),
    )
