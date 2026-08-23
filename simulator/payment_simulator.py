"""Synthetic payment data generator with realistic failure mechanisms.

Produces a pandas DataFrame of payments whose failure probability and failure
reason emerge from customer/method/merchant context rather than pure noise,
including a payment-method degradation incident.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.models.enums import FailureReason, PaymentMethod

METHODS = [PaymentMethod.UPI.value, PaymentMethod.CARD.value,
           PaymentMethod.NETBANKING.value, PaymentMethod.WALLET.value]
_METHOD_WEIGHTS = [0.55, 0.25, 0.14, 0.06]

_SEGMENTS = ["PREMIUM", "REGULAR", "NEW", "CHURN_RISK"]
_SEGMENT_PROB = [0.15, 0.50, 0.25, 0.10]

_CATEGORIES = ["ECOMMERCE", "SAAS", "EDUCATION", "TRAVEL", "UTILITIES"]

# Method baseline failure rates (UPI healthiest, wallets flakiest).
_METHOD_BASE_FAILURE = {"UPI": 0.08, "CARD": 0.12, "NETBANKING": 0.16, "WALLET": 0.20}

_MERCHANT_BASE_SUCCESS = [0.93, 0.90, 0.88, 0.95, 0.91]


def _customer_segment_params(rng: np.random.Generator, segment: str) -> tuple[float, float]:
    """Returns (success_rate, avg_txn_value) for a segment."""
    if segment == "PREMIUM":
        return float(np.clip(rng.beta(20, 2), 0.6, 1.0)), float(rng.lognormal(9.0, 0.5))
    if segment == "REGULAR":
        return float(np.clip(rng.beta(12, 3), 0.5, 1.0)), float(rng.lognormal(7.8, 0.6))
    if segment == "NEW":
        return float(np.clip(rng.beta(8, 4), 0.4, 1.0)), float(rng.lognormal(7.2, 0.7))
    return float(np.clip(rng.beta(4, 6), 0.2, 0.85)), float(rng.lognormal(7.5, 0.6))


def generate_merchants(rng: np.random.Generator, n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "merchant_id": range(n),
        "name": [f"Merchant-{chr(65 + i)}" for i in range(n)],
        "category": rng.choice(_CATEGORIES, size=n),
        "baseline_success_rate": _MERCHANT_BASE_SUCCESS[:n],
    })


def generate_customers(rng: np.random.Generator, n_merchants: int, n_customers: int) -> pd.DataFrame:
    rows = []
    segments = rng.choice(_SEGMENTS, size=n_customers, p=_SEGMENT_PROB)
    for cid in range(n_customers):
        success_rate, avg_value = _customer_segment_params(rng, segments[cid])
        rows.append({
            "customer_id": cid,
            "merchant_id": int(cid % n_merchants),
            "external_customer_id": f"cust_{cid:08d}",
            "segment": segments[cid],
            "success_rate": round(success_rate, 4),
            "avg_value": round(avg_value, 2),
            "preferred_method": str(rng.choice(METHODS)),
        })
    return pd.DataFrame(rows)


def method_failure_rate(method: str, ts_index: pd.DatetimeIndex, incident: tuple[str, str]) -> np.ndarray:
    """Baseline per-method failure rate with a degradation incident window."""
    base = _METHOD_BASE_FAILURE[method]
    rates = np.full(len(ts_index), base)
    start, end = pd.Timestamp(incident[0]), pd.Timestamp(incident[1])
    in_window = (ts_index >= start) & (ts_index <= end)
    # NETBANKING suffers an outage during the incident; others mildly affected.
    if method == "NETBANKING":
        rates[in_window] += 0.35
    else:
        rates[in_window] += 0.03
    return rates


def generate_payments(
    rng: np.random.Generator,
    merchants: pd.DataFrame,
    customers: pd.DataFrame,
    n_payments: int = 50_000,
    seed_date_start: str = "2026-05-01",
    days: int = 90,
    incident: tuple[str, str] = ("2026-06-10", "2026-06-14"),
) -> pd.DataFrame:
    """Generate the transaction log. Failure emerges from context."""
    ts = pd.to_datetime(seed_date_start) + pd.to_timedelta(
        rng.integers(0, days * 24 * 60, size=n_payments), unit="m"
    )
    ts = pd.Series(ts).sort_values().reset_index(drop=True)

    cust_idx = rng.integers(0, len(customers), size=n_payments)
    custs = customers.iloc[cust_idx].reset_index(drop=True)

    methods = np.where(
        rng.random(n_payments) < 0.75,
        custs["preferred_method"],
        rng.choice(METHODS, size=n_payments),
    )

    # Amounts follow the customer's value band (lognormal around their mean).
    amounts = np.round(custs["avg_value"] * rng.lognormal(0, 0.45, size=n_payments), 2)
    amounts = np.clip(amounts, 99, 250_000)

    hours = ts.dt.hour.to_numpy()
    dow = ts.dt.dayofweek.to_numpy()

    # Rolling recent-failure rate per method is approximated by the incident curve.
    method_fail = np.array([
        method_failure_rate(m, pd.DatetimeIndex([t]), incident)[0] for m, t in zip(methods, ts)
    ])

    cust_success = custs["success_rate"].to_numpy()
    merch_success = merchants.set_index("merchant_id").loc[
        custs["merchant_id"]]["baseline_success_rate"].to_numpy()

    # P(fail) combines customer risk, method rail health, merchant baseline, time of day.
    p_fail = (
        (1 - cust_success) * 0.9
        + method_fail
        + (1 - merch_success)
        + np.where((hours < 7) | (hours >= 23), 0.04, 0.0)
    ) / 2.1
    p_fail = np.clip(p_fail, 0.02, 0.75)
    failed = rng.random(n_payments) < p_fail

    reasons = _assign_failure_reasons(rng, failed, methods, method_fail, cust_success, hours)

    df = pd.DataFrame({
        "payment_id": range(n_payments),
        "merchant_id": custs["merchant_id"],
        "customer_id": custs["customer_id"],
        "external_payment_id": [f"pay_{i:09d}" for i in range(n_payments)],
        "amount": amounts,
        "currency": "INR",
        "payment_method": methods,
        "status": np.where(failed, "FAILED", "CAPTURED"),
        "failure_reason": reasons,
        "attempt_number": 1,
        "created_at": ts,
        "hour": hours,
        "day_of_week": dow,
        "recent_method_failure_rate": np.round(method_fail, 4),
        "merchant_success_rate": merch_success,
        "customer_success_rate": cust_success,
        "segment": custs["segment"],
    })
    return df


def _assign_failure_reasons(
    rng: np.random.Generator,
    failed: np.ndarray,
    methods: np.ndarray,
    method_fail: np.ndarray,
    cust_success: np.ndarray,
    hours: np.ndarray,
) -> np.ndarray:
    """Map each failure to a plausible root cause given its context."""
    n = len(failed)
    reasons = np.full(n, "", dtype=object)

    idx = np.where(failed)[0]
    degraded = method_fail[idx] > _METHOD_BASE_FAILURE.get("UPI") + 0.05

    choice = rng.random(len(idx))
    r = np.full(len(idx), FailureReason.UNKNOWN.value, dtype=object)

    r[degraded & (choice < 0.55)] = FailureReason.NETWORK_FAILURE.value
    r[degraded & (choice >= 0.55)] = FailureReason.TEMPORARY_BANK_FAILURE.value

    ok = ~degraded
    c = choice[ok]
    vals = np.full(ok.sum(), FailureReason.UNKNOWN.value, dtype=object)
    vals[c < 0.28] = FailureReason.INSUFFICIENT_FUNDS.value
    vals[(c >= 0.28) & (c < 0.45)] = FailureReason.AUTHENTICATION_FAILURE.value
    vals[(c >= 0.45) & (c < 0.60)] = FailureReason.NETWORK_FAILURE.value
    vals[(c >= 0.60) & (c < 0.72)] = FailureReason.PAYMENT_METHOD_ISSUE.value
    vals[(c >= 0.72) & (c < 0.84)] = FailureReason.CUSTOMER_ABANDONMENT.value
    vals[(c >= 0.84) & (c < 0.92)] = FailureReason.MERCHANT_CONFIGURATION.value
    vals[c >= 0.92] = FailureReason.TEMPORARY_BANK_FAILURE.value

    # Low-history customers abandon more.
    low_hist = cust_success[idx][ok] < 0.6
    swap = low_hist & (rng.random(ok.sum()) < 0.3)
    vals[swap] = FailureReason.CUSTOMER_ABANDONMENT.value

    late_night = hours[idx][ok] >= 23
    vals[late_night & (rng.random(ok.sum()) < 0.35)] = FailureReason.CUSTOMER_ABANDONMENT.value

    r[ok] = vals
    reasons[idx] = r
    return reasons


def add_repeat_attempts(
    rng: np.random.Generator, payments: pd.DataFrame, repeat_fraction: float = 0.18
) -> pd.DataFrame:
    """A share of failed payments already had earlier failed attempts (attempt_number>1)."""
    failed_mask = payments["status"] == "FAILED"
    sample = payments[failed_mask].sample(frac=repeat_fraction, random_state=int(rng.integers(1 << 31)))
    attempts = np.clip(rng.poisson(1.2, size=len(sample)) + 1, 2, 5)
    payments.loc[sample.index, "attempt_number"] = attempts
    payments.loc[sample.index, "failure_reason"] = FailureReason.REPEATED_FAILURE.value
    return payments


def generate_dataset(n_payments: int = 50_000, seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    merchants = generate_merchants(rng)
    customers = generate_customers(rng, len(merchants), n_customers=max(2000, n_payments // 20))
    payments = generate_payments(rng, merchants, customers, n_payments=n_payments)
    payments = add_repeat_attempts(rng, payments)
    return {"merchants": merchants, "customers": customers, "payments": payments}
