"""Decide whether the model has drifted: compare its error on recent actuals with the
error it had in the backtest. If recent error is much worse, retrain."""
from __future__ import annotations

import numpy as np

from .train import mae


def check_drift(predicted: np.ndarray, actual: np.ndarray, backtest_mae: float,
                tolerance: float = 1.5) -> dict:
    recent = mae(predicted, actual)
    ratio = recent / backtest_mae if backtest_mae else float("inf")
    return {"recent_mae": round(recent, 3), "backtest_mae": round(backtest_mae, 3),
            "ratio": round(ratio, 2), "drift": ratio > tolerance}
