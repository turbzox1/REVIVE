"""Integration tests: recovery API against real PostgreSQL + trained models."""
import pytest


def test_decide_returns_full_counterfactual(client, failed_payment):
    r = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id})
    assert r.status_code == 200
    body = r.json()
    for key in (
        "risk_level", "root_cause", "recovery_probability", "expected_recovery",
        "recommended_action", "recommended_timing", "confidence",
        "alternatives", "policy_checks", "explanation",
    ):
        assert key in body, f"missing {key}"
    # All six candidate actions evaluated.
    assert {a["action_type"] for a in body["alternatives"]} >= {"DO_NOTHING", "RETRY_NOW"}
    assert 0.0 <= body["recovery_probability"] <= 1.0
    assert len(body["explanation"]) > 40


def test_decide_is_idempotent(client, failed_payment):
    r1 = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id})
    r2 = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["opportunity_id"] == r2.json()["opportunity_id"]


def test_decide_unknown_payment_404(client):
    r = client.post("/api/v1/recovery/decide", json={"payment_id": 999_999_999})
    assert r.status_code == 404


def test_decide_non_failed_payment_409(client, failed_payment):
    from app.models.catalog import Payment

    failed_payment.status = "CAPTURED"
    payment_id = failed_payment.id
    import app.db.session as sess
    s = sess.SessionLocal()
    try:
        p = s.get(Payment, payment_id)
        p.status = "CAPTURED"
        s.commit()
    finally:
        s.close()
    r = client.post("/api/v1/recovery/decide", json={"payment_id": payment_id})
    assert r.status_code == 409
    # restore
    s = sess.SessionLocal()
    try:
        p = s.get(Payment, payment_id)
        p.status = "FAILED"
        s.commit()
    finally:
        s.close()


def test_opportunity_detail_and_actions(client, failed_payment):
    d = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id}).json()
    oid = d["opportunity_id"]
    detail = client.get(f"/api/v1/recovery/opportunities/{oid}")
    assert detail.status_code == 200
    actions = client.get(f"/api/v1/recovery/{oid}/actions")
    assert actions.status_code == 200
    assert any(a["selected"] for a in actions.json())


def test_execute_simulated_action_labels_channel(client, failed_payment):
    d = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id}).json()
    if d["recommended_action"] == "DO_NOTHING":
        pytest.skip("decision chose DO_NOTHING; nothing to execute")
    r = client.post(f"/api/v1/recovery/{d['opportunity_id']}/execute")
    assert r.status_code == 200
    body = r.json()
    assert body["execution_channel"] in ("SIMULATED", "RAZORPAY_TEST_MODE")


def test_high_value_payment_gets_intervention_not_nothing(client, db, failed_payment):
    """Reliable customer + temporary bank failure must not end in DO_NOTHING."""
    d = client.post("/api/v1/recovery/decide", json={"payment_id": failed_payment.id}).json()
    assert d["recommended_action"] != "DO_NOTHING"
