"""Business-level evaluation: DO_NOTHING vs ALWAYS_RETRY vs REVIVE.

Runs all three strategies on the same held-out failed payments using the
ground-truth recovery simulator as the outcome oracle, producing real
measured metrics (no hardcoding).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from ml.training.features import encode_features  # noqa: E402
from ml.training.labels import _row_to_ctx  # noqa: E402
from simulator.recovery_simulator import recovery_probability  # noqa: E402

REVIVE_CANDIDATES = {
    "RETRY_NOW": {"friction": 50.0, "risk_rate": 0.04},
    "RETRY_LATER": {"friction": 50.0, "risk_rate": 0.03},
    "CREATE_PAYMENT_LINK": {"friction": 43.0, "risk_rate": 0.02},
    "ALTERNATE_PAYMENT_METHOD": {"friction": 51.0, "risk_rate": 0.03},
    "SEND_REMINDER": {"friction": 39.0, "risk_rate": 0.02},
}


def _oracle(action: str, ctx, rng: np.random.Generator, timing: str = "30_MINUTES") -> bool:
    """Ground-truth world: did this intervention recover the payment?"""
    return bool(rng.random() < recovery_probability(action, ctx, timing))


def _model_input(row, feature_names: list[str]) -> pd.DataFrame:
    vec = {
        "amount_log": row.amount_log,
        "attempt_number": float(row.attempt_number),
        "customer_previous_payments": float(row.customer_previous_payments),
        "customer_success_rate": row.customer_success_rate,
        "customer_days_since_last_payment": row.customer_days_since_last_payment,
        "hour": float(row.hour),
        "day_of_week": float(row.day_of_week),
        "merchant_success_rate": row.merchant_success_rate,
        "recent_method_failure_rate": row.recent_method_failure_rate,
        "is_repeat_customer": float(row.is_repeat_customer),
        "amount_percentile": row.amount_percentile,
        "method_" + row.payment_method: 1.0,
        "reason_" + row.failure_reason: 1.0,
    }
    return pd.DataFrame(
        [[vec.get(name, 0.0) for name in feature_names]], columns=feature_names
    )


def run_evaluation(n_samples: int = 2000, seed: int = 42) -> dict:
    from app.ml.predictor import registry

    processed = Path("data/processed")
    failed = pd.read_parquet(processed / "failed_payments.parquet")
    sample = failed.sample(n=min(n_samples, len(failed)), random_state=seed)

    X_all = encode_features(failed)
    feature_names = list(X_all.columns)

    strategies = {
        "DO_NOTHING": {"recovered": 0.0, "interventions": 0, "unnecessary": 0},
        "ALWAYS_RETRY": {"recovered": 0.0, "interventions": 0, "unnecessary": 0},
        "REVIVE": {"recovered": 0.0, "interventions": 0, "unnecessary": 0},
    }
    revenue_at_risk = float(sample["amount"].sum())
    revive_actions: dict[str, int] = {}

    for row in sample.itertuples(index=False):
        ctx = _row_to_ctx(row)
        amount = float(row.amount)
        seed_p = int(row.payment_id) + seed

        # --- Baseline A: DO NOTHING ---
        if _oracle("DO_NOTHING", ctx, np.random.default_rng(seed_p)):
            strategies["DO_NOTHING"]["recovered"] += amount

        # --- Baseline B: ALWAYS RETRY (up to 2 immediate retries) ---
        ar = np.random.default_rng(seed_p)
        for _ in range(2):
            strategies["ALWAYS_RETRY"]["interventions"] += 1
            if _oracle("RETRY_NOW", ctx, ar, timing="NOW"):
                strategies["ALWAYS_RETRY"]["recovered"] += amount
                break
        else:
            # Two retries against a customer who would have paid organically.
            pass

        # --- Strategy C: REVIVE ---
        rv = np.random.default_rng(seed_p)
        X = _model_input(row, feature_names)
        best_action, best_nev = "DO_NOTHING", 0.0
        for action, costs in REVIVE_CANDIDATES.items():
            model = registry.bundle["models"].get(action)
            p = float(model.predict_proba(X)[0][1]) if model is not None else 0.02
            risk = max(amount * costs["risk_rate"] * max(row.attempt_number, 1), 2.0)
            nev = p * amount - costs["friction"] - risk
            if nev > best_nev:
                best_action, best_nev = action, nev

        revive_actions[best_action] = revive_actions.get(best_action, 0) + 1
        if best_action == "DO_NOTHING":
            if _oracle("DO_NOTHING", ctx, rv):
                strategies["REVIVE"]["recovered"] += amount
            elif amount < 100:
                strategies["REVIVE"]["unnecessary"] += 1
        else:
            strategies["REVIVE"]["interventions"] += 1
            if _oracle(best_action, ctx, rv):
                strategies["REVIVE"]["recovered"] += amount

    results = []
    base_recovered = strategies["DO_NOTHING"]["recovered"]
    for name, s in strategies.items():
        results.append({
            "strategy": name,
            "revenue_at_risk": round(revenue_at_risk, 2),
            "revenue_recovered": round(s["recovered"], 2),
            "recovery_rate": round(s["recovered"] / revenue_at_risk, 4),
            "interventions": s["interventions"],
            "unnecessary_interventions": s["unnecessary"],
            "average_recovery_value": round(
                s["recovered"] / s["interventions"], 2
            ) if s["interventions"] else 0.0,
            "incremental_revenue": (
                None if name == "DO_NOTHING"
                else round(s["recovered"] - base_recovered, 2)
            ),
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transactions_evaluated": len(sample),
        "strategies": results,
        "revive_action_distribution": revive_actions,
    }


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2000
    out = run_evaluation(n)
    print(json.dumps(out, indent=2))
