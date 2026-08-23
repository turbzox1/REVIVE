"""REVIVE end-to-end demo: three deterministic scenarios against live PostgreSQL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.catalog import Customer, Payment  # noqa: E402
from app.services.recovery_service import decide_payment  # noqa: E402

LINE = "=" * 72


def _print_decision(r: dict) -> None:
    print(f"  amount          ₹{float(r['expected_recovery']) / r['recovery_probability']:,.0f}"
          if r["recovery_probability"] else "  amount          n/a")
    print(f"  risk            {r['risk_level']}")
    print(f"  root cause      {r['root_cause']}")
    print(f"  probability     {r['recovery_probability']:.0%}")
    print(f"  action          {r['recommended_action']} @ {r['recommended_timing']}")
    print(f"  expected net    ₹{r['expected_recovery']:,.0f}")
    print(f"  confidence      {r['confidence']:.0%}")
    for s in r["alternatives"]:
        flag = "" if s["policy_valid"] else " [policy-rejected]"
        print(f"    - {s['action_type']:<26} NEV ₹{s['net_expected_value']:>10,.0f}{flag}")
    print(f"\n  EXPLANATION: {r['explanation']}\n")


def scenario_1(db) -> int | None:
    """High-value, reliable repeat customer, first failure."""
    row = db.execute(
        select(Payment.id)
        .join(Customer, Customer.id == Payment.customer_id)
        .where(
            Payment.status == "FAILED",
            Payment.amount > 12000,
            Payment.attempt_number == 1,
            Customer.success_rate > 0.85,
        )
        .order_by(func.random())
        .limit(1)
    ).scalar()
    return int(row) if row else None


def scenario_2(db) -> int | None:
    """Low value, repeated failure, churn-risk customer."""
    row = db.execute(
        select(Payment.id)
        .join(Customer, Customer.id == Payment.customer_id)
        .where(
            Payment.status == "FAILED",
            Payment.amount < 400,
            Customer.segment.in_(("CHURN_RISK", "NEW")),
            Customer.success_rate < 0.6,
        )
        .order_by(Payment.amount.asc())
        .limit(1)
    ).scalar()
    return int(row) if row else None


def scenario_3(db) -> dict | None:
    """NETBANKING degradation incident window: pattern detection."""
    from datetime import datetime

    from sqlalchemy import case

    start, end = datetime(2026, 6, 10), datetime(2026, 6, 15)
    failed_count = func.sum(case((Payment.status == "FAILED", 1), else_=0))

    rows = db.execute(
        select(Payment.payment_method, func.count().label("n"), failed_count.label("fails"))
        .group_by(Payment.payment_method)
    ).all()
    incident_rows = db.execute(
        select(Payment.payment_method, func.count().label("n"), failed_count.label("fails"))
        .where(Payment.created_at >= start, Payment.created_at <= end)
        .group_by(Payment.payment_method)
    ).all()

    def rate(rs):
        return {
            m: (float(f or 0) / float(n)) * 100
            for m, n, f in rs
        }

    baseline_rates, incident_rates = rate(rows), rate(incident_rows)

    # A representative failed NETBANKING payment in the window to run through REVIVE.
    pay_id = db.execute(
        select(Payment.id)
        .where(
            Payment.status == "FAILED",
            Payment.payment_method == "NETBANKING",
            Payment.created_at >= start,
            Payment.created_at <= end,
            Payment.attempt_number == 1,
        )
        .order_by(Payment.amount.desc())
        .limit(1)
    ).scalar()
    return {
        "baseline": baseline_rates,
        "incident": incident_rates,
        "payment_id": int(pay_id) if pay_id else None,
    }


def main() -> None:
    db = SessionLocal()
    try:
        print(LINE)
        print("SCENARIO 1 — High-value recoverable payment")
        print(LINE)
        pid = scenario_1(db)
        if pid:
            print(f"  payment #{pid}\n")
            _print_decision(decide_payment(db, pid))
        else:
            print("  no matching payment found\n")

        print(LINE)
        print("SCENARIO 2 — Low-value / low-probability (restraint)")
        print(LINE)
        pid2 = scenario_2(db)
        if pid2:
            print(f"  payment #{pid2}\n")
            _print_decision(decide_payment(db, pid2))
        else:
            print("  no matching payment found\n")

        print(LINE)
        print("SCENARIO 3 — Payment-method degradation incident")
        print(LINE)
        s3 = scenario_3(db)
        if s3:
            print("  failure rate by method (baseline vs incident window):")
            for m in sorted(s3["incident"]):
                b = s3["baseline"].get(m, 0)
                i = s3["incident"][m]
                marker = "  <<< SPIKE" if i > b * 1.5 else ""
                print(f"    {m:<12} {b:5.1f}% -> {i:5.1f}%{marker}")
            if s3["payment_id"]:
                r = decide_payment(db, s3["payment_id"])
                print(f"\n  highest-value NETBANKING failure routed through REVIVE:")
                print(f"    action={r['recommended_action']} timing={r['recommended_timing']} "
                      f"NEV=₹{r['expected_recovery']:,.0f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
