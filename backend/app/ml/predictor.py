"""Loads trained recovery models and produces action-conditioned predictions."""
from __future__ import annotations

import logging
from pathlib import Path

import joblib

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._bundle: dict | None = None
        self.path = Path(settings.MODEL_DIR) / "recovery_models.joblib"

    @property
    def bundle(self) -> dict:
        if self._bundle is None:
            if not self.path.exists():
                raise FileNotFoundError(
                    f"Models not found at {self.path}. Run: python ml/training/train.py"
                )
            self._bundle = joblib.load(self.path)
            logger.info(
                "model registry loaded",
                extra={"event_data": {"actions": sorted(self._bundle["models"].keys())}},
            )
        return self._bundle

    def predict(self, action: str, encoded_row: list[list[float]]) -> float:
        model = self.bundle["models"].get(action)
        if model is None:
            # Constant predictor (e.g. DO_NOTHING organic rate).
            return 0.02
        import pandas as pd

        X = pd.DataFrame(encoded_row, columns=self.bundle["feature_names"])
        return float(model.predict_proba(X)[0][1])

    def calibration(self, action: str) -> float:
        return 0.15


registry = ModelRegistry()
