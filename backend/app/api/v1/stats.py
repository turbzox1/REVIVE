"""Aggregated dashboard statistics computed live from the database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.catalog import Customer, Payment
from app.models.recovery import RecoveryOpportunity, RecoveryOutcome

router = APIRouter(tags=["stats"])


@router.get("/stats/command-center")
def command_center(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    failed_agg = db.execute(
        select(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(),
        ).where(Payment.status == "FAILED")
    ).one()
    revenue_at_risk = float(failed_agg[0] or 0)
    failed_count = int(failed_agg[1])

    recovered = db.execute(
        select(func.coalesce(func.sum(RecoveryOutcome.recovered_amount), 0))
        .where(RecoveryOutcome.successful.is_(True))
    ).scalar() or 0

    recoverable = db.execute(
        select(func.coalesce(func.sum(RecoveryOpportunity.expected_recovery), 0)).where(
            RecoveryOpportunity.status.in_(("DECIDED", "EXECUTING"))
        )
    ).scalar() or 0

    opportunities_open = db.execute(
        select(func.count()).select_from(RecoveryOpportunity).where(
            RecoveryOpportunity.status.in_(("OPEN", "DECIDED", "EXECUTING"))
        )
    ).scalar()

    by_reason = db.execute(
        select(
            Payment.failure_reason,
            func.count(),
            func.sum(Payment.amount),
        )
        .where(Payment.status == "FAILED")
        .group_by(Payment.failure_reason)
        .order_by(func.sum(Payment.amount).desc())
    ).all()

    # Payment-method health over the trailing window.
    total_by_method = dict(db.execute(
        select(Payment.payment_method, func.count())
        .where(Payment.created_at >= week_ago)
        .group_by(Payment.payment_method)
    ).all())
    failed_by_method = dict(db.execute(
        select(Payment.payment_method, func.count())
        .where(Payment.created_at >= week_ago, Payment.status == "FAILED")
        .group_by(Payment.payment_method)
    ).all())

    method_health = [
        {
            "method": m,
            "failure_rate": round(failed_by_method.get(m, 0) / n, 4) if n else 0,
            "transactions": n,
        }
        for m, n in sorted(total_by_method.items(), key=lambda kv: -kv[1])
    ]

    return {
        "revenue_at_risk": round(revenue_at_risk, 2),
        "failed_payments": failed_count,
        "recoverable_revenue": round(float(recoverable), 2),
        "recovered_revenue": round(float(recovered), 2),
        "recovery_rate": round(float(recovered) / revenue_at_risk, 6) if revenue_at_risk else 0,
        "open_opportunities": int(opportunities_open or 0),
        "by_failure_reason": [
            {"reason": r or "UNKNOWN", "count": c, "amount": round(float(a or 0), 2)}
            for r, c, a in by_reason
        ],
        "payment_method_health": method_health,
    }
