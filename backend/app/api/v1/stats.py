"""Aggregated dashboard statistics computed live from the database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.catalog import Payment
from app.models.recovery import RecoveryOpportunity, RecoveryOutcome

router = APIRouter(tags=["stats"])


@router.get("/stats/command-center")
def command_center(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # ------------------------------------------------------------------
    # CURRENT REVENUE AT RISK
    # ------------------------------------------------------------------
    # Only payments that are currently FAILED are considered unresolved
    # revenue at risk.
    failed_agg = db.execute(
        select(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(),
        ).where(Payment.status == "FAILED")
    ).one()

    revenue_at_risk = float(failed_agg[0] or 0)
    failed_count = int(failed_agg[1])

    # ------------------------------------------------------------------
    # HISTORICAL RECOVERED REVENUE
    # ------------------------------------------------------------------
    # Sum successful recovery outcomes.
    recovered = db.execute(
        select(
            func.coalesce(
                func.sum(RecoveryOutcome.recovered_amount),
                0,
            )
        ).where(
            RecoveryOutcome.successful.is_(True)
        )
    ).scalar() or 0

    recovered_revenue = float(recovered)

    # ------------------------------------------------------------------
    # RECOVERY FUNNEL BASE
    # ------------------------------------------------------------------
    # Revenue that entered the recovery funnel consists of:
    #
    #   CURRENT UNRESOLVED REVENUE AT RISK
    #   +
    #   HISTORICALLY RECOVERED REVENUE
    #
    # Example:
    #   ₹15,000 currently failed
    #   ₹30,000 historically recovered
    #   --------------------------------
    #   ₹45,000 recovery funnel
    #
    # This prevents recovery rate from becoming misleading
    # (e.g. ₹30,000 recovered / ₹15,000 currently failed).
    recovery_base = revenue_at_risk + recovered_revenue

    # ------------------------------------------------------------------
    # CURRENTLY RECOVERABLE REVENUE
    # ------------------------------------------------------------------
    # Opportunities that have been decided but are not yet completed.
    recoverable = db.execute(
        select(
            func.coalesce(
                func.sum(RecoveryOpportunity.expected_recovery),
                0,
            )
        ).where(
            RecoveryOpportunity.status.in_(
                ("DECIDED", "EXECUTING")
            )
        )
    ).scalar() or 0

    recoverable_revenue = float(recoverable)

    # ------------------------------------------------------------------
    # OPEN RECOVERY OPPORTUNITIES
    # ------------------------------------------------------------------
    opportunities_open = db.execute(
        select(func.count())
        .select_from(RecoveryOpportunity)
        .where(
            RecoveryOpportunity.status.in_(
                ("OPEN", "DECIDED", "EXECUTING")
            )
        )
    ).scalar() or 0

    # ------------------------------------------------------------------
    # FAILURE REASONS
    # ------------------------------------------------------------------
    by_reason = db.execute(
        select(
            Payment.failure_reason,
            func.count(),
            func.sum(Payment.amount),
        )
        .where(
            Payment.status == "FAILED"
        )
        .group_by(
            Payment.failure_reason
        )
        .order_by(
            func.sum(Payment.amount).desc()
        )
    ).all()

    # ------------------------------------------------------------------
    # PAYMENT METHOD HEALTH
    # ------------------------------------------------------------------
    # Calculate payment-method failure rate over the last 7 days.
    total_by_method = dict(
        db.execute(
            select(
                Payment.payment_method,
                func.count(),
            )
            .where(
                Payment.created_at >= week_ago
            )
            .group_by(
                Payment.payment_method
            )
        ).all()
    )

    failed_by_method = dict(
        db.execute(
            select(
                Payment.payment_method,
                func.count(),
            )
            .where(
                Payment.created_at >= week_ago,
                Payment.status == "FAILED",
            )
            .group_by(
                Payment.payment_method
            )
        ).all()
    )

    method_health = [
        {
            "method": method,
            "failure_rate": round(
                failed_by_method.get(method, 0) / transaction_count,
                4,
            ) if transaction_count else 0,
            "transactions": transaction_count,
        }
        for method, transaction_count
        in sorted(
            total_by_method.items(),
            key=lambda item: -item[1],
        )
    ]

    # ------------------------------------------------------------------
    # RECOVERY RATE
    # ------------------------------------------------------------------
    # Percentage of the recovery funnel that has actually been recovered.
    recovery_rate = (
        round(
            recovered_revenue / recovery_base,
            6,
        )
        if recovery_base
        else 0
    )

    # ------------------------------------------------------------------
    # COMMAND CENTER RESPONSE
    # ------------------------------------------------------------------
    return {
        "revenue_at_risk": round(
            revenue_at_risk,
            2,
        ),

        "failed_payments": failed_count,

        "recoverable_revenue": round(
            recoverable_revenue,
            2,
        ),

        "recovered_revenue": round(
            recovered_revenue,
            2,
        ),

        "recovery_base": round(
            recovery_base,
            2,
        ),

        "recovery_rate": recovery_rate,

        "open_opportunities": int(
            opportunities_open or 0
        ),

        "by_failure_reason": [
            {
                "reason": reason or "UNKNOWN",
                "count": count,
                "amount": round(
                    float(amount or 0),
                    2,
                ),
            }
            for reason, count, amount in by_reason
        ],

        "payment_method_health": method_health,
    }