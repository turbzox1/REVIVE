"""Seed one FAILED payment in the container DB using the app's ORM layer."""
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import Customer, Merchant, MerchantPolicy, Order, Payment

db = SessionLocal()
tag = str(int(datetime.now().timestamp()))
merchant = Merchant(name=f"E2E-{tag}", category="TEST", baseline_success_rate=0.9)
db.add(merchant)
db.flush()
db.add(MerchantPolicy(
    merchant_id=merchant.id, max_retries=3, max_notifications=2,
    minimum_retry_interval_minutes=30, max_recovery_amount=1_000_000,
    allow_payment_links=True, allow_automatic_retry=True,
    friction_cost_per_notification=35.0, friction_cost_per_retry=45.0,
))
customer = Customer(
    merchant_id=merchant.id, external_customer_id=f"e2e-cust-{tag}",
    segment="PREMIUM", preferred_method="UPI", failed_transactions=0,
    success_rate=0.95, total_transactions=20, successful_transactions=19,
    average_transaction_value=5000,
)
db.add(customer)
db.flush()
order = Order(
    merchant_id=merchant.id, customer_id=customer.id,
    external_order_id=f"e2e-order-{tag}", amount=15000, currency="INR",
    status="ATTEMPTED",
)
db.add(order)
db.flush()
payment = Payment(
    order_id=order.id, merchant_id=merchant.id, customer_id=customer.id,
    external_payment_id=f"e2e-pay-{tag}", amount=15000, currency="INR",
    payment_method="CARD", status="FAILED",
    failure_reason="TEMPORARY_BANK_FAILURE", attempt_number=1,
    created_at=datetime.now(timezone.utc) - timedelta(hours=1),
)
db.add(payment)
db.commit()
print(f"PAYMENT_ID={payment.id}")
db.close()
