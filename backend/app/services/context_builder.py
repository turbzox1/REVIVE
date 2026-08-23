"""Builds model features and recovery context from live database state."""
from __future__ import annotations

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Customer as CustomerORM
from app.models.catalog import Merchant as MerchantORM
from app.models.catalog import Payment as PaymentORM
from app.services.recovery_context import RecoveryContext as Ctx


def build_feature_row(db: Session, payment: PaymentORM) -> dict:
    """Reconstructs the exact feature vector used during training."""
    customer = db.get(CustomerORM, payment.customer_id)
    merchant = db.get(MerchantORM, payment.merchant_id)

    prev_count = db.scalar(
        select(func.count(PaymentORM.id)).where(
            PaymentORM.customer_id == payment.customer_id,
            PaymentORM.created_at < payment.created_at,
        )
    )
    last_seen = db.scalar(
        select(func.max(PaymentORM.created_at)).where(
            PaymentORM.customer_id == payment.customer_id,
            PaymentORM.created_at < payment.created_at,
        )
    )
    days_since = (
        (payment.created_at - last_seen).total_seconds() / 86400.0
        if last_seen else 30.0
    )

    week_ago = payment.created_at.timestamp() - 7 * 86400
    window_start = payment.created_at - func.make_interval(0, 0, 0, 7)
    method_total = db.scalar(
        select(func.count(PaymentORM.id)).where(
            PaymentORM.payment_method == payment.payment_method,
            PaymentORM.created_at >= window_start,
            PaymentORM.created_at < payment.created_at,
        )
    ) or 0
    method_failed = db.scalar(
        select(func.count(PaymentORM.id)).where(
            PaymentORM.payment_method == payment.payment_method,
            PaymentORM.status == "FAILED",
            PaymentORM.created_at >= window_start,
            PaymentORM.created_at < payment.created_at,
        )
    ) or 0
    recent_method_failure_rate = (method_failed / method_total) if method_total else 0.08

    rank = db.scalar(
        select(func.count(PaymentORM.id)).where(
            PaymentORM.merchant_id == payment.merchant_id,
            PaymentORM.amount < payment.amount,
        )
    ) or 0
    total_m = db.scalar(
        select(func.count(PaymentORM.id)).where(
            PaymentORM.merchant_id == payment.merchant_id,
        )
    ) or 1

    return {
        "amount_log": float(np.log1p(max(float(payment.amount), 0))),
        "payment_method": payment.payment_method,
        "failure_reason": payment.failure_reason or "UNKNOWN",
        "attempt_number": int(payment.attempt_number),
        "customer_previous_payments": int(prev_count or 0),
        "customer_success_rate": float(customer.success_rate),
        "customer_days_since_last_payment": float(days_since),
        "hour": payment.created_at.hour,
        "day_of_week": payment.created_at.weekday(),
        "merchant_success_rate": float(merchant.baseline_success_rate),
        "recent_method_failure_rate": float(recent_method_failure_rate),
        "is_repeat_customer": int(prev_count >= 2),
        "amount_percentile": float(rank / max(total_m, 1)),
    }


def encode_row(features: dict, feature_names: list[str]) -> list[list[float]]:
    """One-hot encode a single feature dict to match training columns."""
    methods = ["UPI", "CARD", "NETBANKING", "WALLET"]
    reasons = [
        "TEMPORARY_BANK_FAILURE", "INSUFFICIENT_FUNDS", "AUTHENTICATION_FAILURE",
        "NETWORK_FAILURE", "PAYMENT_METHOD_ISSUE", "CUSTOMER_ABANDONMENT",
        "REPEATED_FAILURE", "MERCHANT_CONFIGURATION", "UNKNOWN",
    ]
    vec = {}
    numeric = {k: v for k, v in features.items() if k not in ("payment_method", "failure_reason")}
    vec.update(numeric)
    for m in methods:
        vec[f"method_{m}"] = 1.0 if features["payment_method"] == m else 0.0
    for r in reasons:
        vec[f"reason_{r}"] = 1.0 if features["failure_reason"] == r else 0.0
    return [[vec.get(name, 0.0) for name in feature_names]]


def build_recovery_context(db: Session, payment: PaymentORM, features: dict) -> Ctx:
    return Ctx(
        customer_success_rate=features["customer_success_rate"],
        customer_total_payments=features["customer_previous_payments"],
        amount=float(payment.amount),
        amount_percentile=features["amount_percentile"],
        payment_method=payment.payment_method,
        failure_reason=features["failure_reason"],
        attempt_number=features["attempt_number"],
        merchant_success_rate=features["merchant_success_rate"],
        recent_method_failure_rate=features["recent_method_failure_rate"],
        hour=features["hour"],
        day_of_week=features["day_of_week"],
        days_since_last_payment=features["customer_days_since_last_payment"],
    )
