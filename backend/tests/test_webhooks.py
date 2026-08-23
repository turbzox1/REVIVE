"""Webhook tests: idempotency, signature validation, graceful processing."""
import hashlib
import hmac as hmac_lib

from app.core.config import settings


def _payload(event_id: str) -> dict:
    return {
        "id": event_id,
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"notes": {"revive_payment_id": "59"}}}},
    }


def test_duplicate_webhook_ignored_once(client, db):
    p = _payload("evt_test_dup_001")
    r1 = client.post("/api/v1/webhooks/razorpay", json=p)
    r2 = client.post("/api/v1/webhooks/razorpay", json=p)
    b1, b2 = r1.json(), r2.json()
    processed_first = (b1.get("status") == "processed") or (b1.get("reason") == "duplicate")
    assert processed_first or b1.get("status") == "stored_with_error"
    assert b2.get("status") == "ignored" and b2.get("reason") == "duplicate"


def test_invalid_signature_rejected_when_secret_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "test-secret")
    p = _payload("evt_test_sig_002")
    r = client.post(
        "/api/v1/webhooks/razorpay",
        json=p,
        headers={"X-Razorpay-Signature": "deadbeef"},
    )
    assert r.json().get("status") == "rejected"


def test_valid_signature_accepted(client, monkeypatch):
    secret = "test-secret-abc"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    p = _payload("evt_test_sig_003")
    raw = str(p).replace("'", '"').encode()  # TestClient signs the JSON it sends; emulate verify path instead
    # Directly exercise the verifier contract:
    good = hmac_lib.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    from app.integrations.razorpay import verify_webhook_signature

    assert verify_webhook_signature(raw, good)
    assert not verify_webhook_signature(raw, "bad")
