"""Razorpay webhook ingestion with idempotency and signature verification."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.integrations.razorpay import verify_webhook_signature
from app.models.catalog import Payment as PaymentORM
from app.models.enums import PaymentStatus
from app.models.ops import WebhookEvent

logger = logging.getLogger(__name__)
router = APIRouter()

RECOVERABLE_EVENTS = {"payment.captured", "payment.authorized", "order.paid"}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    payload = await request.json()

    event_id = payload.get("id") or f"unsigned_{payload.get('event', 'unknown')}_{id(payload)}"
    event_type = payload.get("event", "unknown")

    # Idempotency check first: duplicate delivery is a no-op.
    existing = db.query(WebhookEvent).filter_by(external_event_id=event_id).first()
    if existing is not None:
        logger.info("webhook ignored as duplicate", extra={"event_data": {"event_id": event_id}})
        return {"status": "ignored", "reason": "duplicate"}

    if settings.RAZORPAY_WEBHOOK_SECRET:
        if not verify_webhook_signature(body, x_razorpay_signature or ""):
            logger.warning("webhook signature invalid", extra={"event_data": {"event_id": event_id}})
            return {"status": "rejected", "reason": "invalid_signature"}

    event = WebhookEvent(
        external_event_id=event_id,
        event_type=event_type,
        payload=payload,
        processed=False,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "ignored", "reason": "duplicate"}

    error = _process_event(db, event_type, payload)
    event.processed = error is None
    event.process_error = error
    event.processed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("webhook processed", extra={
        "event_data": {"event_id": event_id, "type": event_type, "error": error},
    })
    return {"status": "processed" if error is None else "stored_with_error", "detail": error}


def _process_event(db: Session, event_type: str, payload: dict) -> str | None:
    """Applies the webhook to domain state. Out-of-order events converge here."""
    try:
        entity = payload.get("payload", {})
        notes = (
            entity.get("payment", {}).get("entity", {}).get("notes", {})
            or entity.get("order", {}).get("entity", {}).get("notes", {})
        )
        payment_id = notes.get("revive_payment_id")
        if payment_id is None:
            return None  # not a REVIVE-originated payment; store only

        payment = db.get(PaymentORM, int(payment_id))
        if payment is None:
            return None

        if event_type in RECOVERABLE_EVENTS:
            payment.status = PaymentStatus.CAPTURED.value if event_type != "payment.authorized" \
                else PaymentStatus.AUTHORIZED.value
        elif event_type == "payment.failed":
            payment.status = PaymentStatus.FAILED.value
        db.commit()
        return None
    except Exception as exc:  # keep webhook ingest resilient
        db.rollback()
        return str(exc)
