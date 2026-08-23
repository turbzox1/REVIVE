"""Build action-conditioned training labels using the recovery outcome simulator.

For every failed payment, we evaluate each candidate action through the
ground-truth simulator and draw a Bernoulli outcome. This produces the
supervised dataset: features -> P(success | action, context).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.enums import RecoveryActionType, Timing  # noqa: E402
from simulator.recovery_simulator import RecoveryContext, recovery_probability  # noqa: E402

ACTIONS = [
    RecoveryActionType.DO_NOTHING.value,
    RecoveryActionType.RETRY_NOW.value,
    RecoveryActionType.RETRY_LATER.value,
    RecoveryActionType.CREATE_PAYMENT_LINK.value,
    RecoveryActionType.ALTERNATE_PAYMENT_METHOD.value,
    RecoveryActionType.SEND_REMINDER.value,
]

TIMINGS = [t.value for t in Timing]


def _row_to_ctx(row) -> RecoveryContext:
    return RecoveryContext(
        customer_success_rate=float(row.customer_success_rate),
        customer_total_payments=int(row.customer_previous_payments),
        amount=float(row.amount),
        amount_percentile=float(row.amount_percentile),
        payment_method=row.payment_method,
        failure_reason=row.failure_reason,
        attempt_number=int(row.attempt_number),
        merchant_success_rate=float(row.merchant_success_rate),
        recent_method_failure_rate=float(row.recent_method_failure_rate),
        hour=int(row.hour),
        day_of_week=int(row.day_of_week),
        days_since_last_payment=float(row.customer_days_since_last_payment),
    )


def build_action_labels(failed_df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Returns long-format frame: one row per (payment, action) with sampled outcome."""
    rng = np.random.default_rng(seed)
    records = []
    for row in failed_df.itertuples(index=False):
        ctx = _row_to_ctx(row)
        for action in ACTIONS:
            timing = rng.choice(TIMINGS) if action == "RETRY_LATER" else "30_MINUTES"
            p = recovery_probability(action, ctx, timing)
            outcome = int(rng.random() < p)
            records.append({
                "payment_id": int(row.payment_id),
                "action_type": action,
                "timing": timing,
                "true_probability": p,
                "recovered": outcome,
            })
    return pd.DataFrame(records)


if __name__ == "__main__":
    data_dir = Path("data/synthetic")
    payments = pd.read_csv(data_dir / "payments.csv", parse_dates=["created_at"])
    customers = pd.read_csv(data_dir / "customers.csv")

    from ml.training.features import build_features

    feats = build_features(payments, customers)
    failed = feats[feats["status"] == "FAILED"]
    labels = build_action_labels(failed)
    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)
    failed.to_parquet(out / "failed_payments.parquet", index=False)
    labels.to_parquet(out / "action_labels.parquet", index=False)
    print(f"failed payments: {len(failed)}, label rows: {len(labels)}")
