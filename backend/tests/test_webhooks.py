"""Webhook tests: idempotency, signature validation, graceful processing.

All deliveries are signed with a known test secret so the suite is
deterministic whether or not RAZORPAY_WEBHOOK_SECRET is configured.
"""
import hashlib
import hmac as hmac_lib
import json
import uuid

import pytest

from app.core.config import settings

TEST_SECRET = "test-webhook-secret"


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _signed_post(client, payload: dict, event_id: str | None = None):
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac_lib.new(TEST_SECRET.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
    }
    if event_id:
        headers["X-Razorpay-Event-Id"] = event_id
    return client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)


def _payload(event_id: str) -> dict:
    return {
        "id": event_id,
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"notes": {"revive_payment_id": "59"}}}},
    }


@pytest.fixture(autouse=True)
def _known_secret(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_SECRET)


def test_duplicate_webhook_ignored_once(client, db):
    p = _payload(f"evt_test_dup_{_uid()}")
    r1 = _signed_post(client, p)
    r2 = _signed_post(client, p)
    b1, b2 = r1.json(), r2.json()
    processed_first = (b1.get("status") == "processed") or (b1.get("reason") == "duplicate")
    assert processed_first or b1.get("status") == "stored_with_error"
    assert b2.get("status") == "ignored" and b2.get("reason") == "duplicate"


def test_header_event_id_idempotency_without_body_id(client, db):
    """Real Razorpay deliveries: event id arrives only via X-Razorpay-Event-Id."""
    p = {"event": "payment.captured",
         "payload": {"payment": {"entity": {"notes": {"revive_payment_id": "59"}}}}}
    eid = f"evt_hdr_dup_{_uid()}"
    r1 = _signed_post(client, p, event_id=eid)
    r2 = _signed_post(client, p, event_id=eid)
    assert r1.json()["status"] in ("processed", "stored_with_error")
    assert r2.json() == {"status": "ignored", "reason": "duplicate"}


def test_invalid_signature_rejected_when_secret_configured(client):
    p = _payload(f"evt_test_sig_{_uid()}")
    body = json.dumps(p, separators=(",", ":")).encode()
    r = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert r.json().get("status") == "rejected"


def test_valid_signature_accepted(client, db):
    p = _payload(f"evt_test_sig_{_uid()}")
    r = _signed_post(client, p)
    assert r.status_code == 200
    assert r.json()["status"] in ("processed", "stored_with_error")


def test_verifier_contract():
    from app.integrations.razorpay import verify_webhook_signature

    raw = b'{"x":1}'
    good = hmac_lib.new(TEST_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(raw, good)
    assert not verify_webhook_signature(raw, "bad")


def test_captured_webhook_finalizes_pending_recovery(client, db, failed_payment):
    """A captured payment settles the PENDING attempt/outcome from a link execution."""
    from app.models.catalog import PaymentAttempt
    from app.models.enums import OpportunityStatus, OutcomeResult
    from app.models.recovery import RecoveryAction, RecoveryOpportunity, RecoveryOutcome

    tag = str(failed_payment.id)
    opp = RecoveryOpportunity(
        payment_id=failed_payment.id, customer_id=failed_payment.customer_id,
        merchant_id=failed_payment.merchant_id, risk_level="LOW",
        root_cause="TEMPORARY_BANK_FAILURE", status=OpportunityStatus.EXECUTING.value,
        recommended_action="CREATE_PAYMENT_LINK",
    )
    db.add(opp)
    db.flush()
    action = RecoveryAction(
        recovery_opportunity_id=opp.id, action_type="CREATE_PAYMENT_LINK",
        predicted_probability=0.5, expected_recovery=100, selected=True,
    )
    db.add(action)
    db.flush()
    outcome = RecoveryOutcome(
        recovery_action_id=action.id, outcome=OutcomeResult.PENDING.value,
        recovered_amount=0, successful=False, actual_friction=0,
        execution_channel="RAZORPAY_TEST_MODE", external_reference="https://rzp.io/x",
    )
    db.add(outcome)
    attempt = PaymentAttempt(
        payment_id=failed_payment.id, attempt_number=2,
        action_type="PAYMENT_LINK", status="PENDING",
    )
    db.add(attempt)
    db.commit()

    try:
        payload = {
            "id": f"evt_capture_{tag}",
            "event": "payment.captured",
            "payload": {"payment": {"entity": {
                "notes": {"revive_payment_id": str(failed_payment.id)},
            }}},
        }
        r = _signed_post(client, payload)
        assert r.json()["status"] == "processed"

        db.expire_all()
        db.refresh(failed_payment)
        assert failed_payment.status == "CAPTURED"
        db.refresh(outcome)
        assert outcome.outcome == OutcomeResult.RECOVERED.value
        assert outcome.successful is True
        assert float(outcome.recovered_amount) == float(failed_payment.amount)
        assert outcome.completed_at is not None
        db.refresh(attempt)
        assert attempt.status == "SUCCESS" and attempt.completed_at is not None
        db.refresh(opp)
        assert opp.status == OpportunityStatus.RECOVERED.value
    finally:
        db.query(RecoveryOutcome).filter_by(id=outcome.id).delete()
        db.query(RecoveryAction).filter_by(id=action.id).delete()
        db.query(RecoveryOpportunity).filter_by(id=opp.id).delete()
        db.query(PaymentAttempt).filter_by(id=attempt.id).delete()
        failed_payment.status = "FAILED"
        db.commit()
