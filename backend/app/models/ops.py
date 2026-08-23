"""Webhook events and merchant intervention policies."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_event_id: Mapped[str] = mapped_column(String(120), unique=True)

    event_type: Mapped[str] = mapped_column(String(60), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)

    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    process_error: Mapped[str | None] = mapped_column(String(500))

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id"), unique=True, index=True
    )

    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    max_notifications: Mapped[int] = mapped_column(Integer, default=2)
    minimum_retry_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    max_recovery_amount: Mapped[float] = mapped_column(default=1_000_000)

    allow_payment_links: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_automatic_retry: Mapped[bool] = mapped_column(Boolean, default=True)

    friction_cost_per_notification: Mapped[float] = mapped_column(default=10.0)
    friction_cost_per_retry: Mapped[float] = mapped_column(default=15.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
