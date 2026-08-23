"""Counterfactual recovery outcome simulation.

Given a failed payment's context, estimates P(success) for each candidate
recovery action. These functions define the *ground truth* world that both
the synthetic dataset labels and the evaluation harness use. The ML models
learn approximations of this process from data only.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FailureReason, PaymentMethod, RecoveryActionType, Timing


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


# Base recovery probability per action, conditioned on root cause.
_BASE_PROB: dict[str, dict[str, float]] = {
    FailureReason.TEMPORARY_BANK_FAILURE.value: {
        "RETRY_NOW": 0.32, "RETRY_LATER": 0.68, "CREATE_PAYMENT_LINK": 0.58,
        "ALTERNATE_PAYMENT_METHOD": 0.52, "SEND_REMINDER": 0.28,
    },
    FailureReason.INSUFFICIENT_FUNDS.value: {
        "RETRY_NOW": 0.14, "RETRY_LATER": 0.46, "CREATE_PAYMENT_LINK": 0.42,
        "ALTERNATE_PAYMENT_METHOD": 0.38, "SEND_REMINDER": 0.34,
    },
    FailureReason.AUTHENTICATION_FAILURE.value: {
        "RETRY_NOW": 0.52, "RETRY_LATER": 0.44, "CREATE_PAYMENT_LINK": 0.48,
        "ALTERNATE_PAYMENT_METHOD": 0.40, "SEND_REMINDER": 0.30,
    },
    FailureReason.NETWORK_FAILURE.value: {
        "RETRY_NOW": 0.62, "RETRY_LATER": 0.55, "CREATE_PAYMENT_LINK": 0.50,
        "ALTERNATE_PAYMENT_METHOD": 0.46, "SEND_REMINDER": 0.26,
    },
    FailureReason.PAYMENT_METHOD_ISSUE.value: {
        "RETRY_NOW": 0.12, "RETRY_LATER": 0.18, "CREATE_PAYMENT_LINK": 0.50,
        "ALTERNATE_PAYMENT_METHOD": 0.56, "SEND_REMINDER": 0.22,
    },
    FailureReason.CUSTOMER_ABANDONMENT.value: {
        "RETRY_NOW": 0.06, "RETRY_LATER": 0.10, "CREATE_PAYMENT_LINK": 0.16,
        "ALTERNATE_PAYMENT_METHOD": 0.08, "SEND_REMINDER": 0.24,
    },
    FailureReason.REPEATED_FAILURE.value: {
        "RETRY_NOW": 0.04, "RETRY_LATER": 0.07, "CREATE_PAYMENT_LINK": 0.09,
        "ALTERNATE_PAYMENT_METHOD": 0.11, "SEND_REMINDER": 0.06,
    },
    FailureReason.MERCHANT_CONFIGURATION.value: {
        "RETRY_NOW": 0.01, "RETRY_LATER": 0.02, "CREATE_PAYMENT_LINK": 0.03,
        "ALTERNATE_PAYMENT_METHOD": 0.02, "SEND_REMINDER": 0.01,
    },
    FailureReason.UNKNOWN.value: {
        "RETRY_NOW": 0.20, "RETRY_LATER": 0.24, "CREATE_PAYMENT_LINK": 0.26,
        "ALTERNATE_PAYMENT_METHOD": 0.22, "SEND_REMINDER": 0.16,
    },
}

_TIMING_MULT: dict[str, float] = {
    Timing.NOW.value: 0.92,
    Timing.MIN_15.value: 1.00,
    Timing.MIN_30.value: 1.08,
    Timing.HOUR_1.value: 1.04,
    Timing.HOUR_6.value: 0.94,
    Timing.HOUR_24.value: 0.82,
}


def recovery_probability(action: str, ctx: RecoveryContext, timing: str = Timing.MIN_30.value) -> float:
    """Ground-truth P(recovery | action, context). Used for labels & evaluation only."""
    if action == RecoveryActionType.DO_NOTHING.value:
        # Small organic recovery: reliable customers sometimes retry on their own.
        organic = 0.04 if ctx.customer_success_rate > 0.85 else 0.01
        return min(organic, 1.0)

    base = _BASE_PROB.get(ctx.failure_reason, _BASE_PROB[FailureReason.UNKNOWN.value]).get(
        action, 0.10
    )

    p = base
    # Customer reliability drives recovery strongly.
    p *= 0.55 + 0.9 * ctx.customer_success_rate
    # Established customers are easier to recover.
    if ctx.customer_total_payments >= 10:
        p *= 1.10
    elif ctx.customer_total_payments <= 2:
        p *= 0.80
    # High-value tickets are harder to recover.
    p *= 1.0 - 0.35 * ctx.amount_percentile
    # Every prior failed attempt roughly halves remaining odds.
    p *= 0.62 ** max(ctx.attempt_number - 1, 0)
    # A degrading method suppresses retries on the same rail.
    if action in ("RETRY_NOW", "RETRY_LATER"):
        p *= max(1.0 - 1.4 * ctx.recent_method_failure_rate, 0.15)
        if action == "RETRY_LATER" and ctx.recent_method_failure_rate > 0.3:
            p *= 1.15  # waiting out a transient outage helps
    # Merchant competence baseline.
    p *= 0.85 + 0.3 * ctx.merchant_success_rate
    # Late-night interventions convert worse.
    if ctx.hour < 7 or ctx.hour >= 23:
        p *= 0.85
    # Payday effect for insufficient funds at month start.
    if ctx.failure_reason == FailureReason.INSUFFICIENT_FUNDS.value and ctx.day_of_week is not None:
        pass

    p *= _TIMING_MULT.get(timing, 1.0)

    # Action-specific structural notes
    if (
        action == "ALTERNATE_PAYMENT_METHOD"
        and ctx.payment_method != PaymentMethod.UPI.value
        and ctx.recent_method_failure_rate > 0.25
    ):
        p *= 1.12  # switching off a failing rail is extra effective

    return round(min(max(p, 0.0), 0.97), 4)
