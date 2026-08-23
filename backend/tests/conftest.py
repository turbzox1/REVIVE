"""Shared fixtures. All tests run against real PostgreSQL (revive database)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models import Merchant, MerchantPolicy, Payment, Customer, Order


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def policy_factory():
    def make(notification: float = 35.0, retry: float = 45.0) -> MerchantPolicy:
        return MerchantPolicy(
            merchant_id=1, max_retries=3, max_notifications=2,
            minimum_retry_interval_minutes=30, max_recovery_amount=1_000_000,
            allow_payment_links=True, allow_automatic_retry=True,
            friction_cost_per_notification=notification,
            friction_cost_per_retry=retry,
        )
    return make


@pytest.fixture()
def failed_payment(db: Session):
    """A synthetic failed payment isolated from seed data."""
    import time

    tag = f"{int(time.time() * 1000) % 10**10}"
    merchant = Merchant(name=f"TEST-MERCHANT-{tag}", category="TEST", baseline_success_rate=0.9)
    db.add(merchant)
    db.flush()
    db.add(MerchantPolicy(
        merchant_id=merchant.id,
        max_retries=3,
        max_notifications=2,
        minimum_retry_interval_minutes=30,
        max_recovery_amount=1_000_000,
        allow_payment_links=True,
        allow_automatic_retry=True,
        friction_cost_per_notification=35.0,
        friction_cost_per_retry=45.0,
    ))
    customer = Customer(
        merchant_id=merchant.id,
        external_customer_id=f"test-cust-{tag}",
        segment="PREMIUM",
        success_rate=0.95,
        total_transactions=20,
        successful_transactions=19,
        average_transaction_value=5000,
    )
    db.add(customer)
    db.flush()
    order = Order(
        merchant_id=merchant.id, customer_id=customer.id,
        external_order_id=f"test-order-{datetime.now(timezone.utc).timestamp()}",
        amount=15000, currency="INR", status="ATTEMPTED",
    )
    db.add(order)
    db.flush()
    payment = Payment(
        order_id=order.id, merchant_id=merchant.id, customer_id=customer.id,
        external_payment_id=f"test-pay-{datetime.now(timezone.utc).timestamp()}",
        amount=15000, currency="INR",
        payment_method="CARD", status="FAILED",
        failure_reason="TEMPORARY_BANK_FAILURE",
        attempt_number=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(payment)
    db.commit()

    yield payment

    # Cleanup test rows (explicit order to respect FKs).
    from app.models import RecoveryAction, RecoveryOpportunity, ModelPrediction
    from app.models.recovery import RecoveryOutcome

    opps = db.query(RecoveryOpportunity).filter_by(payment_id=payment.id).all()
    opp_ids = [o.id for o in opps]
    action_ids = [
        aid for (aid,) in db.query(RecoveryAction.id)
        .filter(RecoveryAction.recovery_opportunity_id.in_(opp_ids))
        .all()
    ] if opp_ids else []
    if action_ids:
        db.query(RecoveryOutcome).filter(
            RecoveryOutcome.recovery_action_id.in_(action_ids)
        ).delete(synchronize_session=False)
    for o in opps:
        db.query(RecoveryAction).filter_by(recovery_opportunity_id=o.id).delete()
        db.delete(o)
    db.query(ModelPrediction).filter_by(payment_id=payment.id).delete()
    from app.models.catalog import PaymentAttempt
    db.query(PaymentAttempt).filter_by(payment_id=payment.id).delete()
    db.commit()
    db.query(Payment).filter(Payment.id == payment.id).delete()
    db.query(Order).filter(Order.id == order.id).delete()
    db.query(Customer).filter(Customer.id == customer.id).delete()
    db.query(MerchantPolicy).filter(MerchantPolicy.merchant_id == merchant.id).delete()
    db.query(Merchant).filter(Merchant.id == merchant.id).delete()
    db.commit()
