"""Counterfactual decision engine.

For a failed payment: predict recovery per action, price friction/risk,
validate policy, select the highest net-expected-value action and timing.
Deterministic for identical inputs (models + policy + context).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ml.predictor import registry
from app.models.catalog import Payment as PaymentORM
from app.models.enums import OpportunityStatus, RecoveryActionType, RiskLevel, Timing
from app.models.ops import MerchantPolicy
from app.policies import engine as policy_engine
from app.services.context_builder import build_feature_row, build_recovery_context, encode_row

logger = logging.getLogger(__name__)

CANDIDATE_ACTIONS = [
    RecoveryActionType.DO_NOTHING.value,
    RecoveryActionType.RETRY_NOW.value,
    RecoveryActionType.RETRY_LATER.value,
    RecoveryActionType.CREATE_PAYMENT_LINK.value,
    RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value,
    RecoveryActionType.SEND_REMINDER.value,
]

# Relative timing effectiveness curve (from the recovery outcome simulator's
# calibration; the ML models are timing-agnostic at their operating point).
TIMING_CURVE = {
    Timing.NOW.value: 0.92,
    Timing.MIN_15.value: 1.00,
    Timing.MIN_30.value: 1.08,
    Timing.HOUR_1.value: 1.04,
    Timing.HOUR_6.value: 0.94,
    Timing.HOUR_24.value: 0.82,
}


@dataclass
class ScoredAction:
    action_type: str
    timing: str
    predicted_probability: float
    expected_recovery: float
    friction_cost: float
    action_cost: float
    risk_penalty: float
    net_expected_value: float
    policy_valid: bool
    rejection_reasons: list[str]
    policy_checks: list[dict]


def assess_risk(amount_percentile: float, attempt_number: int) -> RiskLevel:
    if amount_percentile >= 0.9 or (amount_percentile >= 0.75 and attempt_number >= 3):
        return RiskLevel.CRITICAL
    if amount_percentile >= 0.75 or attempt_number >= 3:
        return RiskLevel.HIGH
    if amount_percentile >= 0.4:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def confidence_score(p_top: float, p_second: float, customer_payments: int) -> float:
    margin = abs(p_top - p_second)
    base = 0.60 + 0.30 * min(margin * 2.0, 1.0)
    if customer_payments >= 10:
        base += 0.05
    return round(min(base, 0.97), 2)


def decide(db: Session, payment: PaymentORM, policy: MerchantPolicy) -> dict:
    """Runs the full counterfactual evaluation for one failed payment."""
    features = build_feature_row(db, payment)
    encoded = encode_row(features, registry.bundle["feature_names"])
    ctx = build_recovery_context(db, payment, features)
    amount = float(payment.amount)

    scored: list[ScoredAction] = []
    predictions: dict[str, float] = {}

    for action in CANDIDATE_ACTIONS:
        p_base = registry.predict(action, encoded)
        predictions[action] = p_base

        best_timing, best_ev = Timing.MIN_30.value, -1e18
        allowed_timings = (
            [Timing.NOW.value, Timing.MIN_15.value]
            if action == RecoveryActionType.RETRY_NOW.value
            else list(TIMING_CURVE.keys())
        )
        for timing in allowed_timings:
            mult = TIMING_CURVE[timing]
            p_t = min(p_base * mult, 0.97) if action != RecoveryActionType.DO_NOTHING.value else p_base
            ev = (
                p_t * amount
                - policy_engine.friction_cost(policy, action)
                - policy_engine.action_cost(action)
                - policy_engine.risk_penalty(amount, action, payment.attempt_number)
            )
            if ev > best_ev:
                best_timing, best_ev = timing, ev

        verdict = policy_engine.evaluate_policy(
            db=db, payment=payment, action_type=action, timing=best_timing,
            policy=policy, prior_recovery_actions=[],
        )

        scored.append(ScoredAction(
            action_type=action,
            timing=best_timing,
            predicted_probability=round(p_base, 4),
            expected_recovery=round(p_base * amount, 2),
            friction_cost=policy_engine.friction_cost(policy, action),
            action_cost=policy_engine.action_cost(action),
            risk_penalty=policy_engine.risk_penalty(amount, action, payment.attempt_number),
            net_expected_value=round(best_ev, 2),
            policy_valid=verdict.valid,
            rejection_reasons=verdict.rejection_reasons,
            policy_checks=verdict.checks,
        ))

    # Selection: highest NEV among policy-valid actions; DO_NOTHING is always valid.
    valid = [s for s in scored if s.policy_valid] or [s for s in scored if s.action_type == "DO_NOTHING"]
    selected = max(valid, key=lambda s: s.net_expected_value)

    ranked = sorted((s for s in scored if s.action_type != selected.action_type),
                    key=lambda s: s.net_expected_value, reverse=True)
    p_second = predictions.get(ranked[0].action_type, 0.0) if ranked else 0.0
    confidence = confidence_score(selected.predicted_probability, p_second,
                                  features["customer_previous_payments"])

    decision = {
        "risk_level": assess_risk(features["amount_percentile"], features["attempt_number"]).value,
        "root_cause": features["failure_reason"],
        "recovery_probability": selected.predicted_probability,
        "expected_recovery": selected.expected_recovery,
        "recommended_action": selected.action_type,
        "recommended_timing": selected.timing,
        "confidence": confidence,
        "features": features,
        "scored_actions": scored,
        "selected": selected,
        "policy_checks": selected.policy_checks,
        "all_predictions": predictions,
    }
    logger.info("decision made", extra={"event_data": {
        "payment_id": payment.id, "action": selected.action_type,
        "nev": selected.net_expected_value,
    }})
    return decision
