"""Core commerce entities: merchants, customers, orders, payments, attempts."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AttemptAction, AttemptStatus, PaymentMethod, PaymentStatus


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    baseline_success_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customers: Mapped[list["Customer"]] = relationship(back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_merchant_external", "merchant_id", "external_customer_id",
              unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    external_customer_id: Mapped[str] = mapped_column(String(64))

    segment: Mapped[str] = mapped_column(String(30), default="REGULAR", index=True)
    preferred_method: Mapped[str] = mapped_column(String(20), default=PaymentMethod.UPI.value)

    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=1)

    average_transaction_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    last_transaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notification_count: Mapped[int] = mapped_column(Integer, default=0)
    last_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="customers")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    external_order_id: Mapped[str] = mapped_column(String(64), unique=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[str] = mapped_column(String(24), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    external_payment_id: Mapped[str] = mapped_column(String(64), unique=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    payment_method: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(default=PaymentStatus.FAILED.value, index=True)

    failure_reason: Mapped[str | None] = mapped_column(String(40), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(40))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)

    action_type: Mapped[str] = mapped_column(default=AttemptAction.INITIAL.value)
    status: Mapped[str] = mapped_column(default=AttemptStatus.PENDING.value, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(40))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
