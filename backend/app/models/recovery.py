"""Recovery domain: opportunities, candidate actions, outcomes, model predictions."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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
from app.models.enums import OpportunityStatus, OutcomeResult


class RecoveryOpportunity(Base):
    __tablename__ = "recovery_opportunities"
    __table_args__ = (Index("ix_opp_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), unique=True, index=True
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)

    risk_level: Mapped[str] = mapped_column(String(12), index=True)
    root_cause: Mapped[str] = mapped_column(String(40))

    recovery_probability: Mapped[float | None] = mapped_column(Float)
    expected_recovery: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    recommended_action: Mapped[str | None] = mapped_column(String(40))
    recommended_timing: Mapped[str | None] = mapped_column(String(16))

    confidence: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(
        default=OpportunityStatus.OPEN.value, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    actions: Mapped[list["RecoveryAction"]] = relationship(back_populates="opportunity")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    recovery_opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_opportunities.id"), index=True
    )

    action_type: Mapped[str] = mapped_column(String(40), index=True)
    timing: Mapped[str | None] = mapped_column(String(16))

    predicted_probability: Mapped[float] = mapped_column(Float)
    expected_recovery: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    friction_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    action_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    risk_penalty: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_expected_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_rejection_reasons: Mapped[list | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    opportunity: Mapped["RecoveryOpportunity"] = relationship(back_populates="actions")
    outcome: Mapped["RecoveryOutcome | None"] = relationship(back_populates="action")


class RecoveryOutcome(Base):
    __tablename__ = "recovery_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recovery_action_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_actions.id"), unique=True, index=True
    )

    outcome: Mapped[str] = mapped_column(default=OutcomeResult.PENDING.value, index=True)
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)

    execution_channel: Mapped[str] = mapped_column(String(30))
    external_reference: Mapped[str | None] = mapped_column(String(120))
    actual_friction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    action: Mapped["RecoveryAction"] = relationship(back_populates="outcome")


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    __table_args__ = (Index("ix_pred_payment_model", "payment_id", "model_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)

    model_name: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(20))
    action_type: Mapped[str] = mapped_column(String(40), index=True)

    prediction: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    features_snapshot: Mapped[dict] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
