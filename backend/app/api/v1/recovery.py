"""Recovery API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.recovery import RecoveryAction, RecoveryOpportunity, RecoveryOutcome
from app.schemas import (
    CandidateActionOut,
    DecideRequest,
    DecisionResponse,
    ExecuteResponse,
    OpportunityListOut,
    PolicyCheckOut,
)
from app.services import recovery_service
from app.services.explanation import generate_explanation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/decide", response_model=DecisionResponse)
def decide(payload: DecideRequest, db: Session = Depends(get_db)):
    try:
        result = recovery_service.decide_payment(db, payload.payment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result


@router.get("/opportunities")
def list_opportunities(
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(RecoveryOpportunity).order_by(desc(RecoveryOpportunity.created_at))
    if status:
        q = q.filter(RecoveryOpportunity.status == status)
    rows = q.offset(offset).limit(limit).all()
    return [
        {
            "id": r.id, "payment_id": r.payment_id, "customer_id": r.customer_id,
            "merchant_id": r.merchant_id, "risk_level": r.risk_level,
            "root_cause": r.root_cause, "recommended_action": r.recommended_action,
            "expected_recovery": float(r.expected_recovery) if r.expected_recovery else None,
            "recovery_probability": r.recovery_probability,
            "recommended_timing": r.recommended_timing,
            "confidence": r.confidence, "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    opp = db.get(RecoveryOpportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    actions = (
        db.query(RecoveryAction)
        .filter_by(recovery_opportunity_id=opp.id)
        .order_by(desc(RecoveryAction.net_expected_value))
        .all()
    )
    outcome = (
        db.query(RecoveryOutcome)
        .join(RecoveryAction, RecoveryOutcome.recovery_action_id == RecoveryAction.id)
        .filter(RecoveryAction.recovery_opportunity_id == opp.id)
        .first()
    )

    payment = recovery_service.get_payment_or_404(db, opp.payment_id)

    decision_view = {
        "selected": type("S", (), {
            "action_type": next((a.action_type for a in actions if a.selected), None),
            "timing": opp.recommended_timing,
            "predicted_probability": opp.recovery_probability,
            "net_expected_value": float(opp.expected_recovery or 0),
            "friction_cost": 0,
            "scored_actions": [],
        })(),
        "scored_actions": actions,
        "features": {"customer_success_rate": 0, "customer_previous_payments": 0},
        "root_cause": opp.root_cause,
        "risk_level": opp.risk_level,
        "recommended_action": opp.recommended_action,
        "recommended_timing": opp.recommended_timing,
        "confidence": opp.confidence,
        "expected_recovery": float(opp.expected_recovery or 0),
    }

    return {
        **{k: getattr(opp, k) for k in (
            "id", "payment_id", "customer_id", "merchant_id", "risk_level",
            "root_cause", "recovery_probability", "expected_recovery",
            "recommended_action", "recommended_timing", "confidence", "status",
            "created_at",
        )},
        "expected_recovery": float(opp.expected_recovery) if opp.expected_recovery else None,
        "actions": [
            {
                "action_type": a.action_type, "timing": a.timing,
                "predicted_probability": a.predicted_probability,
                "expected_recovery": float(a.expected_recovery),
                "friction_cost": float(a.friction_cost),
                "action_cost": float(a.action_cost),
                "risk_penalty": float(a.risk_penalty),
                "net_expected_value": float(a.net_expected_value),
                "selected": a.selected, "policy_valid": a.policy_valid,
                "rejection_reasons": a.policy_rejection_reasons or [],
            }
            for a in actions
        ],
        "outcome": {
            "outcome": outcome.outcome,
            "recovered_amount": float(outcome.recovered_amount),
            "execution_channel": outcome.execution_channel,
            "external_reference": outcome.external_reference,
            "completed_at": outcome.completed_at,
        } if outcome else None,
    }


@router.post("/{opportunity_id}/execute", response_model=ExecuteResponse)
def execute(opportunity_id: int, db: Session = Depends(get_db)):
    from app.integrations.razorpay import resolve_execution_channel

    def channel_resolver(action_type: str):
        return resolve_execution_channel(db, opportunity_id, action_type)

    try:
        result = recovery_service.execute_decision(
            db, opportunity_id, channel_resolver=channel_resolver
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.get("/{opportunity_id}/actions")
def opportunity_actions(opportunity_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(RecoveryAction)
        .filter_by(recovery_opportunity_id=opportunity_id)
        .order_by(desc(RecoveryAction.net_expected_value))
        .all()
    )
    return [
        {
            "action_type": a.action_type, "timing": a.timing,
            "predicted_probability": a.predicted_probability,
            "expected_recovery": float(a.expected_recovery),
            "friction_cost": float(a.friction_cost),
            "action_cost": float(a.action_cost),
            "risk_penalty": float(a.risk_penalty),
            "net_expected_value": float(a.net_expected_value),
            "selected": a.selected, "policy_valid": a.policy_valid,
        }
        for a in rows
    ]


@router.get("/{opportunity_id}/outcome")
def opportunity_outcome(opportunity_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(RecoveryOutcome)
        .join(RecoveryAction, RecoveryOutcome.recovery_action_id == RecoveryAction.id)
        .filter(RecoveryAction.recovery_opportunity_id == opportunity_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="no outcome recorded yet")
    return {
        "outcome": row.outcome,
        "successful": row.successful,
        "recovered_amount": float(row.recovered_amount),
        "execution_channel": row.execution_channel,
        "external_reference": row.external_reference,
        "completed_at": row.completed_at,
    }
