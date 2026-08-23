"""Pydantic request/response schemas (never expose ORM models directly)."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    FailureReason,
    OpportunityStatus,
    PaymentMethod,
    RecoveryActionType,
    RiskLevel,
    Timing,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- commerce ----------


class MerchantOut(ORMModel):
    id: int
    name: str
    category: str
    baseline_success_rate: float


class CustomerOut(ORMModel):
    id: int
    merchant_id: int
    external_customer_id: str
    segment: str
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    success_rate: float
    average_transaction_value: Decimal


class PaymentOut(ORMModel):
    id: int
    order_id: int
    merchant_id: int
    customer_id: int
    external_payment_id: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    failure_reason: str | None
    failure_code: str | None
    attempt_number: int
    created_at: datetime


# ---------- recovery ----------


class CandidateActionOut(BaseModel):
    action_type: RecoveryActionType
    timing: Timing | None = None
    predicted_probability: float
    expected_recovery: Decimal
    friction_cost: Decimal
    action_cost: Decimal
    risk_penalty: Decimal
    net_expected_value: Decimal
    policy_valid: bool = True
    rejection_reasons: list[str] = Field(default_factory=list)


class PolicyCheckOut(BaseModel):
    check: str
    passed: bool
    detail: str


class DecideRequest(BaseModel):
    payment_id: int


class DecisionResponse(BaseModel):
    payment_id: int
    opportunity_id: int
    risk_level: RiskLevel
    root_cause: FailureReason | str
    recovery_probability: float
    expected_recovery: Decimal
    recommended_action: RecoveryActionType
    recommended_timing: Timing | None
    confidence: float
    alternatives: list[CandidateActionOut]
    policy_checks: list[PolicyCheckOut]
    explanation: str


class ExecuteResponse(BaseModel):
    opportunity_id: int
    action_type: RecoveryActionType
    execution_channel: str
    outcome: str
    recovered_amount: Decimal
    external_reference: str | None = None
    message: str


class OpportunityListOut(ORMModel):
    id: int
    payment_id: int
    customer_id: int
    merchant_id: int
    risk_level: str
    root_cause: str
    recommended_action: str | None
    expected_recovery: Decimal | None
    recovery_probability: float | None
    status: OpportunityStatus | str
    created_at: datetime


# ---------- evaluation ----------


class StrategyMetrics(BaseModel):
    strategy: str
    revenue_at_risk: Decimal
    revenue_recovered: Decimal
    recovery_rate: float
    interventions: int
    unnecessary_interventions: int
    average_recovery_value: Decimal
    incremental_revenue: Decimal | None = None


class EvaluationSummary(BaseModel):
    generated_at: datetime
    transactions_evaluated: int
    strategies: list[StrategyMetrics]
    ml_metrics: dict | None = None
