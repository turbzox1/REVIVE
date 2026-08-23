"""Policy / guardrail engine.

Validates proposed recovery actions against merchant policy and customer
friction budgets. This layer is authoritative: neither the decision engine
nor any AI agent can bypass it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Payment as PaymentORM
from app.models.enums import RecoveryActionType, Timing
from app.models.ops import MerchantPolicy
from app.models.recovery import RecoveryAction

NOTIFICATION_ACTIONS = {
    RecoveryActionType.CREATE_PAYMENT_LINK.value,
    RecoveryActionType.RESEND_PAYMENT_LINK.value,
    RecoveryActionType.SEND_REMINDER.value,
}
RETRY_ACTIONS = {
    RecoveryActionType.RETRY_NOW.value,
    RecoveryActionType.RETRY_LATER.value,
    RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value,
}


@dataclass
class PolicyVerdict:
    valid: bool
    checks: list[dict] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    def add(self, check: str, passed: bool, detail: str) -> None:
        self.checks.append({"check": check, "passed": passed, "detail": detail})
        if not passed:
            self.valid = False
            self.rejection_reasons.append(f"{check}: {detail}")


def _timedelta(timing: str) -> timedelta:
    return {
        Timing.NOW.value: timedelta(0),
        Timing.MIN_15.value: timedelta(minutes=15),
        Timing.MIN_30.value: timedelta(minutes=30),
        Timing.HOUR_1.value: timedelta(hours=1),
        Timing.HOUR_6.value: timedelta(hours=6),
        Timing.HOUR_24.value: timedelta(hours=24),
    }.get(timing, timedelta(0))


def evaluate_policy(
    db: Session,
    payment: PaymentORM,
    action_type: str,
    timing: str,
    policy: MerchantPolicy,
    prior_recovery_actions: list[RecoveryAction],
) -> PolicyVerdict:
    verdict = PolicyVerdict(valid=True)
    now = datetime.now(timezone.utc)

    retries_used = payment.attempt_number - 1 + sum(
        1 for a in prior_recovery_actions if a.action_type in {v.value for v in RETRY_ACTIONS}
    )
    notifications_sent = sum(
        1 for a in prior_recovery_actions if a.action_type in NOTIFICATION_ACTIONS
    )

    # 1. Action eligibility / merchant permissions.
    if action_type == RecoveryActionType.CREATE_PAYMENT_LINK.value or \
       action_type == RecoveryActionType.RESEND_PAYMENT_LINK.value:
        verdict.add("allow_payment_links", policy.allow_payment_links,
                    "merchant permits payment links" if policy.allow_payment_links else "payment links disabled by merchant")

    if action_type in RETRY_ACTIONS and \
       action_type != RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value:
        verdict.add("allow_automatic_retry", policy.allow_automatic_retry,
                    "merchant permits automatic retry" if policy.allow_automatic_retry else "automatic retry disabled by merchant")

    # 2. Retry budget.
    if action_type in RETRY_ACTIONS:
        within = retries_used < policy.max_retries
        verdict.add("max_retries", within,
                    f"{retries_used}/{policy.max_retries} retries used")
        if action_type == RecoveryActionType.RETRY_NOW.value and retries_used > 0:
            interval_ok = policy.minimum_retry_interval_minutes == 0
            verdict.add("minimum_retry_interval", interval_ok,
                        f"policy requires >= {policy.minimum_retry_interval_minutes} min between retries"
                        if not interval_ok else "no minimum interval configured")

    # 3. Notification / friction budget.
    if action_type in NOTIFICATION_ACTIONS:
        within = notifications_sent < policy.max_notifications
        verdict.add("max_notifications", within,
                    f"{notifications_sent}/{policy.max_notifications} notifications used")

    # 4. Amount ceiling.
    amount_ok = float(payment.amount) <= float(policy.max_recovery_amount)
    verdict.add("max_recovery_amount", amount_ok,
                f"₹{float(payment.amount):,.0f} vs limit ₹{float(policy.max_recovery_amount):,.0f}")

    return verdict


def friction_cost(policy: MerchantPolicy, action_type: str) -> float:
    """Customer friction cost of an intervention (₹ equivalent)."""
    if action_type == RecoveryActionType.DO_NOTHING.value:
        return 0.0
    if action_type in NOTIFICATION_ACTIONS:
        return float(policy.friction_cost_per_notification)
    if action_type == RecoveryActionType.ESCALATE_TO_MERCHANT.value:
        return 50.0
    return float(policy.friction_cost_per_retry)


def action_cost(action_type: str) -> float:
    """Direct operational cost of executing the action (₹)."""
    return {
        RecoveryActionType.DO_NOTHING.value: 0.0,
        RecoveryActionType.RETRY_NOW.value: 5.0,
        RecoveryActionType.RETRY_LATER.value: 5.0,
        RecoveryActionType.CREATE_PAYMENT_LINK.value: 8.0,
        RecoveryActionType.RESEND_PAYMENT_LINK.value: 4.0,
        RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value: 6.0,
        RecoveryActionType.SEND_REMINDER.value: 4.0,
        RecoveryActionType.ESCALATE_TO_MERCHANT.value: 40.0,
    }.get(action_type, 5.0)


def risk_penalty(amount: float, action_type: str, attempt_number: int) -> float:
    """Churn/brand risk penalty — grows with intrusiveness and repeated attempts."""
    if action_type == RecoveryActionType.DO_NOTHING.value:
        return 0.0
    intrusive = {
        RecoveryActionType.RETRY_NOW.value: 0.04,
        RecoveryActionType.RETRY_LATER.value: 0.03,
        RecoveryActionType.CREATE_PAYMENT_LINK.value: 0.02,
        RecoveryActionType.RESEND_PAYMENT_LINK.value: 0.03,
        RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value: 0.03,
        RecoveryActionType.SEND_REMINDER.value: 0.02,
        RecoveryActionType.ESCALATE_TO_MERCHANT.value: 0.01,
    }.get(action_type, 0.02)
    return round(max(amount * intrusive * max(attempt_number, 1), 2.0), 2)
