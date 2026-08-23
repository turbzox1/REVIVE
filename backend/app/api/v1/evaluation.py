"""Evaluation API: serves measured strategy comparison and ML metrics."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.recovery import ModelPrediction

router = APIRouter(tags=["evaluation"])

EVAL_PATH = Path(settings.MODEL_DIR).parents[1] / "data" / "processed" / "evaluation_summary.json"


def _load_evaluation() -> dict | None:
    if EVAL_PATH.exists():
        return json.loads(EVAL_PATH.read_text())
    return None


@router.get("/evaluation/summary")
def evaluation_summary(db: Session = Depends(get_db)) -> dict:
    data = _load_evaluation()
    if data is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transactions_evaluated": 0,
            "strategies": [],
            "note": "run scripts/run_evaluation.py to generate metrics",
        }
    ml_metrics = _ml_metrics(db)
    if ml_metrics is not None:
        data["ml_metrics"] = ml_metrics
    return data


@router.get("/evaluation/baseline")
def evaluation_baseline() -> dict:
    data = _load_evaluation()
    if data is None:
        return {"available": False}
    by_name = {s["strategy"]: s for s in data["strategies"]}
    base, revive = by_name.get("DO_NOTHING"), by_name.get("REVIVE")
    retry = by_name.get("ALWAYS_RETRY")
    return {
        "available": True,
        "transactions": data["transactions_evaluated"],
        "do_nothing": base,
        "always_retry": retry,
        "revive": revive,
        "incremental_vs_do_nothing": revive["incremental_revenue"] if revive else None,
        "incremental_vs_always_retry": (
            round(revive["revenue_recovered"] - retry["revenue_recovered"], 2)
            if revive and retry else None
        ),
        "intervention_reduction_pct": (
            round((1 - revive["interventions"] / retry["interventions"]) * 100, 1)
            if revive and retry and retry["interventions"] else None
        ),
    }


def _ml_metrics(db: Session) -> dict | None:
    path = Path(settings.MODEL_DIR) / "metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
