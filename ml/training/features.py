"""Feature engineering for recovery models."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    "amount_log",
    "payment_method",
    "failure_reason",
    "attempt_number",
    "customer_previous_payments",
    "customer_success_rate",
    "customer_days_since_last_payment",
    "hour",
    "day_of_week",
    "merchant_success_rate",
    "recent_method_failure_rate",
    "is_repeat_customer",
    "amount_percentile",
]

CATEGORICAL = ["payment_method", "failure_reason"]


def build_features(payments: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Join payments with customer aggregates and engineer model features.

    Input: synthetic payments frame (with hour/day_of_week/etc.) + customers.
    Output: one row per payment with FEATURES columns.
    """
    df = payments.merge(
        customers[["customer_id", "success_rate", "segment"]],
        on="customer_id",
        suffixes=("", "_cust"),
    )

    df["customer_previous_payments"] = df.groupby("customer_id").cumcount()
    df["is_repeat_customer"] = (df["customer_previous_payments"] >= 2).astype(int)

    # days since this customer's previous payment (0 if first seen)
    df = df.sort_values(["customer_id", "created_at"])
    last_seen = df.groupby("customer_id")["created_at"].shift(1)
    df["customer_days_since_last_payment"] = (
        (df["created_at"] - last_seen).dt.total_seconds() / 86400.0
    ).fillna(30.0)

    df["amount_log"] = np.log1p(df["amount"].clip(lower=0))
    df["customer_success_rate"] = df["success_rate"].astype(float)

    # transaction value percentile within merchant
    df["amount_percentile"] = df.groupby("merchant_id")["amount"].rank(pct=True)

    return df


def encode_features(df: pd.DataFrame):
    """One-hot categorical features; returns X dataframe ready for sklearn."""
    X = pd.get_dummies(
        df[FEATURES],
        columns=CATEGORICAL,
        prefix=["method", "reason"],
        dtype=float,
    )
    return X
