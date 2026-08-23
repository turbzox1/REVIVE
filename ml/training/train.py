"""Train action-conditioned recovery models and persist artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from ml.training.features import FEATURES, build_features, encode_features  # noqa: E402
from ml.training.labels import ACTIONS  # noqa: E402

MODEL_DIR = Path("ml/models")
MODEL_VERSION = "1.0.0"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    processed = Path("data/processed")
    failed = pd.read_parquet(processed / "failed_payments.parquet")
    labels = pd.read_parquet(processed / "action_labels.parquet")
    return failed, labels


def train_models(n_payments: int | None = None) -> dict:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    failed, labels = load_data()
    if n_payments:
        failed = failed[failed["payment_id"].isin(failed["payment_id"].head(n_payments))]

    X = encode_features(failed)
    y = failed["payment_id"]
    feature_names = list(X.columns)

    metrics: dict = {"models": {}, "feature_names": feature_names, "model_version": MODEL_VERSION}
    models: dict[str, object] = {}

    for action in ACTIONS:
        sub = labels[labels["action_type"] == action]
        merged = sub.merge(
            failed[["payment_id"]].assign(_pid=failed["payment_id"]),
            left_on="payment_id", right_on="payment_id", how="inner",
        )
        # Align X rows to label rows by payment order.
        x_idx = failed.reset_index().set_index("payment_id").loc[sub["payment_id"], "index"]
        Xa = X.loc[x_idx].reset_index(drop=True)
        ya = sub["recovered"].reset_index(drop=True)

        # 70/15/15 split (train/val/test) — stratified where possible.
        X_train, X_tmp, y_train, y_tmp = train_test_split(
            Xa, ya, test_size=0.30, random_state=42,
            stratify=None if ya.nunique() < 2 else ya,
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_tmp, y_tmp, test_size=0.50, random_state=42,
            stratify=None if y_tmp.nunique() < 2 else y_tmp,
        )

        if action == "DO_NOTHING" or ya.nunique() < 2 or len(ya) == 0:
            # Degenerate case: store constant predictor metadata.
            const = float(ya.mean()) if len(ya) else 0.0
            metrics["models"][action] = {
                "type": "constant", "constant": const,
                "roc_auc": None, "note": "insufficient variance",
            }
            continue

        gb = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, max_depth=None,
            random_state=42, early_stopping=True, validation_fraction=0.1,
        )
        gb.fit(X_train, y_train)

        val_proba = gb.predict_proba(X_val)[:, 1]
        test_proba = gb.predict_proba(X_test)[:, 1]
        test_pred = (test_proba >= 0.5).astype(int)

        m = {
            "type": "hist_gradient_boosting",
            "roc_auc": round(float(roc_auc_score(y_test, test_proba)), 4),
            "precision": round(float(precision_score(y_test, test_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, test_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, test_pred, zero_division=0)), 4),
            "brier_calibration": round(float(brier_score_loss(y_test, test_proba)), 4),
            "test_rows": int(len(y_test)),
        }
        metrics["models"][action] = m
        models[action] = gb

    joblib.dump({"models": models, "feature_names": feature_names}, MODEL_DIR / "recovery_models.joblib")
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics["models"], indent=2))
    return metrics


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else None
    train_models(n)
