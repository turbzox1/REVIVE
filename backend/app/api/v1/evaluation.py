"""Evaluation API: serves measured strategy comparison and ML metrics."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["evaluation"])

EVAL_PATH = (
    Path(settings.MODEL_DIR).parents[1]
    / "data"
    / "processed"
    / "evaluation_summary.json"
)


def _load_evaluation() -> dict | None:
    """Load the precomputed evaluation summary if it exists."""
    if not EVAL_PATH.exists():
        return None

    try:
        return json.loads(EVAL_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


@router.get("/evaluation/summary")
def evaluation_summary(db: Session = Depends(get_db)) -> dict:
    """Return strategy evaluation results and ML model metrics."""
    data = _load_evaluation()

    if data is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transactions_evaluated": 0,
            "strategies": [],
            "revive_action_distribution": {},
            "ml_metrics": None,
            "note": "run scripts/run_evaluation.py to generate metrics",
        }

    # Work on a copy so the loaded JSON isn't unexpectedly mutated.
    data = dict(data)

    ml_metrics = _ml_metrics()

    if ml_metrics is not None:
        data["ml_metrics"] = ml_metrics

    return data


@router.get("/evaluation/baseline")
def evaluation_baseline() -> dict:
    """Return the baseline comparison between strategies."""
    data = _load_evaluation()

    if data is None:
        return {"available": False}

    strategies = data.get("strategies", [])
    by_name = {
        strategy.get("strategy"): strategy
        for strategy in strategies
        if strategy.get("strategy")
    }

    base = by_name.get("DO_NOTHING")
    retry = by_name.get("ALWAYS_RETRY")
    revive = by_name.get("REVIVE")

    return {
        "available": True,
        "transactions": data.get("transactions_evaluated", 0),
        "do_nothing": base,
        "always_retry": retry,
        "revive": revive,
        "incremental_vs_do_nothing": (
            revive.get("incremental_revenue")
            if revive
            else None
        ),
        "incremental_vs_always_retry": (
            round(
                revive["revenue_recovered"]
                - retry["revenue_recovered"],
                2,
            )
            if revive and retry
            else None
        ),
        "intervention_reduction_pct": (
            round(
                (
                    1
                    - revive["interventions"]
                    / retry["interventions"]
                )
                * 100,
                1,
            )
            if revive
            and retry
            and retry.get("interventions")
            else None
        ),
    }


def _ml_metrics() -> dict | None:
    """Load ML model evaluation metrics from the ML artifact directory."""
    path = Path(settings.MODEL_DIR) / "metrics.json"

    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    return raw