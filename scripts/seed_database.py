"""Load synthetic CSVs into PostgreSQL."""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.init_db import init_db  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Customer,
    Merchant,
    MerchantPolicy,
    Order,
    Payment,
    PaymentAttempt,
)
from app.models.enums import AttemptAction, AttemptStatus  # noqa: E402

DATA_DIR = Path("data/synthetic")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="wipe tables before seeding")
    args = parser.parse_args()

    init_db()
    merchants = pd.read_csv(DATA_DIR / "merchants.csv")
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    payments = pd.read_csv(DATA_DIR / "payments.csv", parse_dates=["created_at"])

    db = SessionLocal()
    try:
        if args.reset:
            for table in (
                PaymentAttempt, Payment, Order, Customer,
                MerchantPolicy, Merchant,
            ):
                db.query(table).delete()
            db.commit()
            print("tables reset")

        merchant_map: dict[int, int] = {}
        for row in merchants.itertuples(index=False):
            m = Merchant(
                name=row.name, category=row.category,
                baseline_success_rate=float(row.baseline_success_rate),
            )
            db.add(m)
            db.flush()
            merchant_map[int(row.merchant_id)] = m.id
            db.add(MerchantPolicy(merchant_id=m.id))

        customer_objs: list[tuple[int, Customer]] = []
        for row in customers.itertuples(index=False):
            c = Customer(
                merchant_id=merchant_map[int(row.merchant_id)],
                external_customer_id=str(row.external_customer_id),
                segment=row.segment,
                preferred_method=row.preferred_method,
                success_rate=float(row.success_rate),
                average_transaction_value=float(row.avg_value),
            )
            db.add(c)
            customer_objs.append((int(row.customer_id), c))
        db.flush()
        cust_map: dict[int, int] = {k: c.id for k, c in customer_objs}

        id_to_cust = {v: k for k, v in cust_map.items()}
        failed_stats: dict[int, list[int]] = {}

        order_rows, payment_rows, attempt_rows = [], [], []
        for row in payments.itertuples(index=False):
            cid = cust_map[int(row.customer_id)]
            o = dict(
                merchant_id=merchant_map[int(row.merchant_id)],
                customer_id=cid,
                external_order_id=f"ord_{row.payment_id:09d}",
                amount=float(row.amount), currency="INR",
                status="PAID" if row.status == "CAPTURED" else "ATTEMPTED",
            )
            p = dict(
                order_id=len(order_rows) + 1,  # placeholder, fixed below
                merchant_id=merchant_map[int(row.merchant_id)],
                customer_id=cid,
                external_payment_id=row.external_payment_id,
                amount=float(row.amount), currency="INR",
                payment_method=row.payment_method, status=row.status,
                failure_reason=row.failure_reason or None,
                failure_code=(row.failure_reason or "NONE"),
                attempt_number=int(row.attempt_number),
                created_at=row.created_at.to_pydatetime(),
            )
            order_rows.append(o)
            payment_rows.append(p)

            if row.status == "FAILED":
                st = failed_stats.setdefault(cid, [0, 0])
                st[0] += 1
                st[1] += 1

        # Bulk insert orders, then payments referencing real order ids.
        from app.models import Order as OrderModel, Payment as PaymentModel
        db.bulk_insert_mappings(OrderModel, order_rows)
        db.flush()
        order_ids = [
            oid for (oid,) in db.query(OrderModel.id).order_by(OrderModel.id).all()
        ]
        for i, pr in enumerate(payment_rows):
            pr["order_id"] = order_ids[i]
        db.bulk_insert_mappings(PaymentModel, payment_rows)
        db.flush()

        # Update customer aggregates from generated history.
        captured_counts = payments[payments["status"] == "CAPTURED"].groupby("customer_id").size()
        for ext_cid, n in captured_counts.items():
            stats = failed_stats.get(cust_map[int(ext_cid)], [0, 0])
            c = db.get(Customer, cust_map[int(ext_cid)])
            c.total_transactions = int(n) + stats[0]
            c.successful_transactions = int(n)
            c.failed_transactions = stats[0]
            c.last_transaction_at = None
        db.commit()

        n_pay = db.query(PaymentModel).count()
        print(f"seeded merchants={len(merchant_map)} customers={len(cust_map)} payments={n_pay}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
