"""Recovery service: orchestrates decision, persistence, and execution."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.catalog import PaymentAttempt
from app.models.catalog import Payment as PaymentORM
from app.models.enums import (
    AttemptAction,
    AttemptStatus,
    ExecutionChannel,
    OpportunityStatus,
    OutcomeResult,
    RecoveryActionType,
)
from app.models.ops import MerchantPolicy
from app.models.recovery import (
    ModelPrediction,
    RecoveryAction,
    RecoveryOpportunity,
)
from app.services.decision_engine import decide
from app.services.explanation import generate_explanation

logger = logging.getLogger(__name__)


def get_payment_or_404(db: Session, payment_id: int) -> PaymentORM | None:
    return db.get(PaymentORM, payment_id)


def get_policy(db: Session, merchant_id: int) -> MerchantPolicy:
    policy = db.query(MerchantPolicy).filter_by(merchant_id=merchant_id).first()
    if policy is None:
        policy = MerchantPolicy(merchant_id=merchant_id)
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def decide_payment(db: Session, payment_id: int) -> dict:
    """Full decision pipeline for a failed payment, persisted to the database."""
    payment = get_payment_or_404(db, payment_id)
    if payment is None:
        raise LookupError(f"payment {payment_id} not found")
    if payment.status != "FAILED":
        raise ValueError(f"payment {payment_id} is not FAILED (status={payment.status})")

    policy = get_policy(db, payment.merchant_id)
    decision = decide(db, payment, policy)

    # Idempotent: re-deciding replaces the previous evaluation.
    opp = db.query(RecoveryOpportunity).filter_by(payment_id=payment.id).first()
    if opp is not None:
        db.query(ModelPrediction).filter_by(payment_id=payment.id).delete()
        db.query(RecoveryAction).filter_by(recovery_opportunity_id=opp.id).delete()
        for field, value in (
            ("risk_level", decision["risk_level"]),
            ("root_cause", decision["root_cause"]),
            ("recovery_probability", decision["recovery_probability"]),
            ("expected_recovery", decision["expected_recovery"]),
            ("recommended_action", decision["recommended_action"]),
            ("recommended_timing", decision["recommended_timing"]),
            ("confidence", decision["confidence"]),
            ("status", OpportunityStatus.DECIDED.value),
        ):
            setattr(opp, field, value)
        db.flush()
    else:
        opp = RecoveryOpportunity(
            payment_id=payment.id,
            customer_id=payment.customer_id,
            merchant_id=payment.merchant_id,
            risk_level=decision["risk_level"],
            root_cause=decision["root_cause"],
            recovery_probability=decision["recovery_probability"],
            expected_recovery=decision["expected_recovery"],
            recommended_action=decision["recommended_action"],
            recommended_timing=decision["recommended_timing"],
            confidence=decision["confidence"],
            status=OpportunityStatus.DECIDED.value,
        )
        db.add(opp)
        db.flush()

    action_rows: dict[str, RecoveryAction] = {}
    for s in decision["scored_actions"]:
        row = RecoveryAction(
            recovery_opportunity_id=opp.id,
            action_type=s.action_type,
            timing=s.timing,
            predicted_probability=s.predicted_probability,
            expected_recovery=s.expected_recovery,
            friction_cost=s.friction_cost,
            action_cost=s.action_cost,
            risk_penalty=s.risk_penalty,
            net_expected_value=s.net_expected_value,
            selected=(s.action_type == decision["recommended_action"]),
            policy_valid=s.policy_valid,
            policy_rejection_reasons=s.rejection_reasons or None,
        )
        db.add(row)
        action_rows[s.action_type] = row

        db.add(ModelPrediction(
            payment_id=payment.id,
            model_name="recovery_gb",
            model_version="1.0.0",
            action_type=s.action_type,
            prediction=s.predicted_probability,
            confidence=decision["confidence"],
            features_snapshot=decision["features"],
        ))

    explanation = generate_explanation(payment=payment, decision=decision)
    db.commit()
    db.refresh(opp)

    logger.info("recovery opportunity created", extra={"event_data": {
        "opportunity_id": opp.id, "payment_id": payment.id,
    }})

    result = _to_response(opp.id, payment.id, decision, explanation)
    return result


def execute_decision(
    db: Session,
    opportunity_id: int,
    channel_resolver=None,
    outcome_simulator=None,
) -> dict:
    """Executes the selected action for an opportunity.

    channel_resolver(action_type) -> ExecutionChannel + external_reference,
    provided by the integrations layer (Razorpay Test Mode where configured).
    outcome_simulator(ctx) -> recovered bool, used only for SIMULATED actions.
    """
    opp = db.get(RecoveryOpportunity, opportunity_id)
    if opp is None:
        raise LookupError(f"opportunity {opportunity_id} not found")

    selected = (
        db.query(RecoveryAction)
        .filter_by(recovery_opportunity_id=opp.id, selected=True)
        .first()
    )
    if selected is None:
        raise ValueError("no selected action for opportunity")

    if selected.action_type == RecoveryActionType.DO_NOTHING.value:
        outcome = RecoveryOutcome_row(
            selected.id, OutcomeResult.NOT_RECOVERED.value, 0.0,
            ExecutionChannel.SIMULATED.value, None,
        )
        db.add(outcome)
        opp.status = OpportunityStatus.LOST.value
        db.commit()
        return {
            "opportunity_id": opp.id,
            "action_type": selected.action_type,
            "execution_channel": ExecutionChannel.SIMULATED.value,
            "outcome": OutcomeResult.NOT_RECOVERED.value,
            "recovered_amount": 0.0,
            "external_reference": None,
            "message": "DO_NOTHING selected: expected value below intervention cost. No customer contacted.",
        }

    channel, external_ref = (channel_resolver or _default_channel)(selected.action_type)

    if channel == ExecutionChannel.RAZORPAY_TEST_MODE.value:
        # Real Test Mode execution: outcome stays PENDING until webhook confirms.
        outcome = RecoveryOutcome_row(
            selected.id, OutcomeResult.PENDING.value, 0.0, channel, external_ref,
        )
        message = f"Executed through Razorpay Test Mode ({external_ref}). Awaiting payment confirmation."
        successful_now = False
    else:
        # Simulated recovery action — honestly labelled as simulation.
        success = bool(outcome_simulator(selected)) if outcome_simulator else False
        amount = float(opp.expected_recovery if success else 0.0)
        outcome = RecoveryOutcome_row(
            selected.id,
            OutcomeResult.RECOVERED.value if success else OutcomeResult.NOT_RECOVERED.value,
            amount if success else 0.0,
            channel, None,
        )
        message = f"Simulated recovery action ({'success' if success else 'no recovery'})."
        successful_now = success

    db.add(outcome)
    db.add(PaymentAttempt(
        payment_id=opp.payment_id,
        attempt_number=opp.recommended_timing and 2 or 2,
        action_type=_attempt_action(selected.action_type),
        status=AttemptStatus.PENDING.value if channel == ExecutionChannel.RAZORPAY_TEST_MODE.value
        else (AttemptStatus.SUCCESS.value if successful_now else AttemptStatus.FAILED.value),
    ))
    opp.status = (
        OpportunityStatus.EXECUTING.value
        if channel == ExecutionChannel.RAZORPAY_TEST_MODE.value
        else (OpportunityStatus.RECOVERED.value if successful_now else OpportunityStatus.LOST.value)
    )
    db.commit()

    logger.info("action executed", extra={"event_data": {
        "opportunity_id": opp.id, "action": selected.action_type, "channel": channel,
    }})
    return {
        "opportunity_id": opp.id,
        "action_type": selected.action_type,
        "execution_channel": channel,
        "outcome": outcome.outcome,
        "recovered_amount": float(outcome.recovered_amount),
        "external_reference": external_ref,
        "message": message,
    }


def _attempt_action(action_type: str) -> str:
    if "LINK" in action_type:
        return AttemptAction.PAYMENT_LINK.value
    if "REMINDER" in action_type:
        return AttemptAction.REMINDER.value
    return AttemptAction.RETRY.value


def RecoveryOutcome_row(action_id, outcome, recovered, channel, ref):
    from app.models.recovery import RecoveryOutcome

    return RecoveryOutcome(
        recovery_action_id=action_id,
        outcome=outcome,
        recovered_amount=recovered,
        successful=outcome == OutcomeResult.RECOVERED.value,
        execution_channel=channel,
        external_reference=ref,
        completed_at=datetime.now(timezone.utc),
    )


def _default_channel(action_type: str) -> tuple[str, str | None]:
    return ExecutionChannel.SIMULATED.value, None


def _to_response(opportunity_id: int, payment_id: int, decision: dict, explanation: str) -> dict:
    return {
        "payment_id": payment_id,
        "opportunity_id": opportunity_id,
        "risk_level": decision["risk_level"],
        "root_cause": decision["root_cause"],
        "recovery_probability": decision["recovery_probability"],
        "expected_recovery": decision["expected_recovery"],
        "recommended_action": decision["recommended_action"],
        "recommended_timing": decision["recommended_timing"],
        "confidence": decision["confidence"],
        "alternatives": [
            {
                "action_type": s.action_type,
                "timing": s.timing,
                "predicted_probability": s.predicted_probability,
                "expected_recovery": s.expected_recovery,
                "friction_cost": s.friction_cost,
                "action_cost": s.action_cost,
                "risk_penalty": s.risk_penalty,
                "net_expected_value": s.net_expected_value,
                "policy_valid": s.policy_valid,
                "rejection_reasons": s.rejection_reasons,
            }
            for s in decision["scored_actions"]
        ],
        "policy_checks": decision["policy_checks"],
        "explanation": explanation,
    }
