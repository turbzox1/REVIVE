"""Shared recovery evaluation context (single source of truth for simulator + runtime)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryContext:
    customer_success_rate: float
    customer_total_payments: int
    amount: float
    amount_percentile: float  # 0..1 within merchant distribution
    payment_method: str
    failure_reason: str
    attempt_number: int
    merchant_success_rate: float
    recent_method_failure_rate: float
    hour: int
    day_of_week: int
    days_since_last_payment: float
