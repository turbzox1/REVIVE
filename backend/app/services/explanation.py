"""Decision explanation layer.

Rule-based by default (deterministic, always available). When an LLM provider
is configured, the structured evidence is passed to the provider for a
merchant-facing narrative — the LLM only ever explains; it cannot act.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalog import Payment as PaymentORM
from app.services.llm.client import get_llm_client

logger = logging.getLogger(__name__)

_ACTION_LABELS = {
    "DO_NOTHING": "do nothing",
    "RETRY_NOW": "retry immediately",
    "RETRY_LATER": "delayed retry",
    "CREATE_PAYMENT_LINK": "send a payment link",
    "RESEND_PAYMENT_LINK": "resend the payment link",
    "ALTERNATE_PAYMENT_METHOD": "switch payment method",
    "SEND_REMINDER": "send a reminder",
}


def _rule_based_explanation(payment: PaymentORM, decision: dict) -> str:
    selected = decision["selected"]
    amount = float(payment.amount)
    parts = [
        f"A ₹{amount:,.0f} payment failed due to {decision['root_cause']}.",
        (
            f"The customer has a {decision['features']['customer_success_rate']*100:.0f}% "
            f"historical success rate across "
            f"{decision['features']['customer_previous_payments']} prior transactions."
        ),
        (
            f"REVIVE recommends to {_ACTION_LABELS.get(selected.action_type, selected.action_type)} "
            f"(timing: {selected.timing}), with a predicted recovery probability of "
            f"{selected.predicted_probability*100:.0f}% and expected net recovery of "
            f"₹{selected.net_expected_value:,.0f} after friction ({selected.friction_cost}) "
            f"and risk costs."
        ),
    ]
    rejected = [s for s in decision["scored_actions"]
                if s.action_type != selected.action_type]
    if rejected:
        best_rejected = max(rejected, key=lambda s: s.net_expected_value)
        parts.append(
            f"'{best_rejected.action_type}' was the closest alternative at ₹"
            f"{best_rejected.net_expected_value:,.0f} net expected value."
        )
    blocked = [s for s in rejected if not s.policy_valid]
    if blocked:
        parts.append(
            f"{len(blocked)} candidate action(s) were rejected by policy: "
            + "; ".join(f"{s.action_type} ({', '.join(s.rejection_reasons)})" for s in blocked[:2])
            + "."
        )
    if selected.action_type == "DO_NOTHING":
        parts.append(
            "Expected recovery does not justify the customer friction and intervention "
            "costs — contacting this customer would destroy value."
        )
    return " ".join(parts)


def generate_explanation(payment: PaymentORM, decision: dict, db: Session | None = None) -> str:
    base = _rule_based_explanation(payment, decision)

    client = get_llm_client()
    if client is None:
        return base

    try:
        narrative = client.explain_decision(_evidence(payment, decision))
        return f"{narrative}\n\n[Deterministic analysis] {base}"
    except Exception as exc:
        logger.warning("LLM explanation unavailable, using rule-based", extra={
            "event_data": {"error": type(exc).__name__},
        })
        return base


def _evidence(payment: PaymentORM, decision: dict) -> dict:
    return {
        "transaction": {
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "method": payment.payment_method,
            "status": payment.status,
            "failure_reason": payment.failure_reason,
            "attempt_number": payment.attempt_number,
        },
        "customer_history": {
            "previous_payments": decision["features"]["customer_previous_payments"],
            "success_rate": decision["features"]["customer_success_rate"],
            "days_since_last_payment": decision["features"]["customer_days_since_last_payment"],
        },
        "candidate_actions": [
            {
                "action_type": s.action_type,
                "predicted_probability": s.predicted_probability,
                "net_expected_value": s.net_expected_value,
                "policy_valid": s.policy_valid,
                "rejection_reasons": s.rejection_reasons,
            }
            for s in decision["scored_actions"]
        ],
        "selected_action": {
            "action_type": decision["recommended_action"],
            "timing": decision["recommended_timing"],
            "expected_recovery": decision["expected_recovery"],
            "confidence": decision["confidence"],
        },
    }
