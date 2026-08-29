"""Razorpay Test Mode integration layer.

CREATE_PAYMENT_LINK executes against Razorpay Test Mode when credentials are
configured; without credentials the caller receives a SIMULATED channel so
the system remains fully demonstrable and honestly labelled.
"""
from __future__ import annotations

import logging

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalog import Customer as CustomerORM
from app.models.catalog import Payment as PaymentORM
from app.models.enums import ExecutionChannel
from app.models.recovery import RecoveryOpportunity

logger = logging.getLogger(__name__)
API_BASE = "https://api.razorpay.com/v1"


def razorpay_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


class RazorpayError(Exception):
    pass


def create_payment_link(db: Session, opportunity_id: int) -> dict:
    """Creates a Test Mode payment link for the opportunity's failed amount."""
    if not razorpay_configured():
        raise RazorpayError("Razorpay credentials not configured")

    opp = db.get(RecoveryOpportunity, opportunity_id)
    payment = db.get(PaymentORM, opp.payment_id)
    customer = db.get(CustomerORM, opp.customer_id)

    resp = requests.post(
        f"{API_BASE}/payment_links/",
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        json={
            "amount": int(float(payment.amount) * 100),  # paise
            "currency": payment.currency,
            "accept_partial": False,
            "reference_id": f"revive_opp_{opp.id}",
            "description": f"REVIVE recovery for payment {payment.external_payment_id}",
            "customer": {
                "name": customer.external_customer_id,
                "contact": "+919123456789",
                "email": f"{customer.external_customer_id}@revive.test",
            },
            "notes": {
                "revive_opportunity_id": str(opp.id),
                "revive_payment_id": str(payment.id),
            },
        },
        timeout=20,
    )
    if resp.status_code >= 300:
        logger.warning("razorpay payment link failed", extra={
            "event_data": {"status": resp.status_code},
        })
        raise RazorpayError(f"Razorpay API error {resp.status_code}")
    data = resp.json()
    return {"id": data["id"], "short_url": data["short_url"]}


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verifies X-Razorpay-Signature (HMAC-SHA256 of raw body with webhook secret)."""
    import hashlib
    import hmac as hmac_lib

    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac_lib.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(expected, signature or "")


def resolve_execution_channel(db: Session, opportunity_id: int, action_type: str):
    """Decides real vs simulated execution for an action at execute-time."""
    if action_type == "CREATE_PAYMENT_LINK" and razorpay_configured():
        try:
            link = create_payment_link(db, opportunity_id)
            return ExecutionChannel.RAZORPAY_TEST_MODE.value, link["short_url"]
        except RazorpayError as exc:
            logger.warning("razorpay execution unavailable, simulating", extra={
                "event_data": {"error": str(exc)},
            })
            # Fall through to simulated with explicit note.
    if action_type == "CREATE_PAYMENT_LINK":
        return (ExecutionChannel.SIMULATED.value,
                "simulated-link (set RAZORPAY_KEY_ID/SECRET for Test Mode)")
    return ExecutionChannel.SIMULATED.value, None
