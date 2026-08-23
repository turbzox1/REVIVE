"""Unit tests: policy/guardrail engine."""
from datetime import datetime, timezone

from app.models.catalog import Payment
from app.models.enums import OpportunityStatus, RecoveryActionType
from app.models.ops import MerchantPolicy
from app.models.recovery import RecoveryAction
from app.policies.engine import evaluate_policy


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _payment(attempt_number: int = 1):
    return Payment(
        id=999, order_id=1, merchant_id=1, customer_id=1,
        external_payment_id="x", amount=18_000, currency="INR",
        payment_method="CARD", status="FAILED", attempt_number=attempt_number,
        created_at=datetime.now(timezone.utc),
    )


def _policy(**over):
    defaults = dict(
        merchant_id=1, max_retries=3, max_notifications=2,
        minimum_retry_interval_minutes=30, max_recovery_amount=25_000,
        allow_payment_links=True, allow_automatic_retry=True,
        friction_cost_per_notification=35.0, friction_cost_per_retry=45.0,
    )
    defaults.update(over)
    return MerchantPolicy(**defaults)


def test_all_valid_when_within_budgets(db):
    v = evaluate_policy(db, _payment(), "RETRY_NOW", "NOW", _policy(), [])
    assert v.valid
    assert all(c["passed"] for c in v.checks)


def test_max_retries_blocks_retry():
    prior = [Row(action_type="RETRY_NOW"), Row(action_type="RETRY_LATER")]
    v = evaluate_policy(None, _payment(attempt_number=2), "RETRY_LATER", "30_MINUTES", _policy(max_retries=3), prior)
    assert not v.valid
    assert any(c["check"] == "max_retries" and not c["passed"] for c in v.checks)


def test_payment_links_disabled_by_merchant():
    v = evaluate_policy(None, _payment(), "CREATE_PAYMENT_LINK", "30_MINUTES", _policy(allow_payment_links=False), [])
    assert not v.valid
    assert any("allow_payment_links" in r for r in v.rejection_reasons)


def test_automatic_retry_disabled_by_merchant():
    v = evaluate_policy(None, _payment(), "RETRY_LATER", "30_MINUTES", _policy(allow_automatic_retry=False), [])
    assert not v.valid


def test_min_retry_interval_blocks_immediate_retry_on_second_attempt():
    v = evaluate_policy(None, _payment(attempt_number=2), "RETRY_NOW", "NOW", _policy(minimum_retry_interval_minutes=30), [])
    assert not v.valid
    assert any(c["check"] == "minimum_retry_interval" and not c["passed"] for c in v.checks)


def test_amount_ceiling():
    v = evaluate_policy(None, _payment(), "CREATE_PAYMENT_LINK", "30_MINUTES", _policy(max_recovery_amount=10_000), [])
    assert not v.valid


def test_do_nothing_always_passes():
    v = evaluate_policy(None, _payment(), "DO_NOTHING", "NOW", _policy(), [Row(action_type="RETRY_NOW")] * 5)
    assert v.valid
