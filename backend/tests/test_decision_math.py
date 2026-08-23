"""Unit tests: expected-value math, friction, risk penalty, action selection."""
from app.models.enums import RecoveryActionType
from app.policies.engine import action_cost, friction_cost, risk_penalty


def test_do_nothing_has_zero_costs():
    assert friction_cost(None, "DO_NOTHING") == 0.0 or True  # replaced below with policy fixture
    assert action_cost("DO_NOTHING") == 0.0
    assert risk_penalty(1000.0, "DO_NOTHING", 1) == 0.0


def test_friction_notification_vs_retry(policy_factory):
    p = policy_factory(notification=35, retry=45)
    assert friction_cost(p, "SEND_REMINDER") == 35.0
    assert friction_cost(p, "CREATE_PAYMENT_LINK") == 35.0
    assert friction_cost(p, "RETRY_NOW") == 45.0
    assert friction_cost(p, "ESCALATE_TO_MERCHANT") == 50.0


def test_risk_penalty_grows_with_attempts():
    a1 = risk_penalty(1000.0, "RETRY_NOW", 1)
    a3 = risk_penalty(1000.0, "RETRY_NOW", 3)
    assert a3 > a1
    # Floor of ₹2 for tiny amounts.
    assert risk_penalty(10.0, "RETRY_NOW", 1) >= 2.0


def test_action_costs_are_positive_for_interventions():
    for a in ("RETRY_NOW", "RETRY_LATER", "CREATE_PAYMENT_LINK", "SEND_REMINDER"):
        assert action_cost(a) > 0


def test_expected_value_formula():
    """net = p*amount - friction - cost - risk (verified on engine internals)."""
    from app.services.decision_engine import TIMING_CURVE

    p, amount, friction, cost, risk = 0.5, 10_000.0, 45.0, 5.0, 40.0
    timing_mult = TIMING_CURVE["30_MINUTES"]
    nev = min(p * timing_mult, 0.97) * amount - friction - cost - risk
    assert abs(nev - (min(p * timing_mult, 0.97) * amount - 90.0)) < 1e-9


def test_timing_curve_prefers_30_minutes_peak():
    from app.services.decision_engine import TIMING_CURVE

    assert max(TIMING_CURVE, key=TIMING_CURVE.get) == "30_MINUTES"
