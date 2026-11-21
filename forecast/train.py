"""Backtest the candidate models, keep the best, and save it as a JSON artifact.

    python -m forecast.train data/alarms.csv models/model.json

Rolling-origin backtest: train on everything up to day T, forecast the next `horizon`
days, move T forward, repeat. This mimics how the model is really used.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .models import MODELS


def mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def backtest(model_cls, y: np.ndarray, horizon: int = 14, folds: int = 6) -> float:
    errors = []
    for k in range(folds, 0, -1):
        cut = len(y) - k * horizon
        model = model_cls().fit(y[:cut])
        errors.append(mae(model.predict(horizon), y[cut:cut + horizon]))
    return float(np.mean(errors))


def train(df: pd.DataFrame, horizon: int = 14) -> dict:
    y = df["alarms"].to_numpy(dtype=float)
    scores = {name: backtest(cls, y, horizon) for name, cls in MODELS.items()}
    best = min(scores, key=scores.get)
    model = MODELS[best]().fit(y)
    return {
        "model": best,
        "state": model.state(),
        "backtest_mae": {k: round(v, 3) for k, v in scores.items()},
        "horizon": horizon,
        "data_end": str(pd.to_datetime(df["date"]).max().date()),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def save_atomic(artifact: dict, path: Path) -> None:
    """Write to a temp file then rename, so the API never reads a half-written model."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(artifact, f, indent=2)
    os.replace(tmp, path)


def main() -> None:
    data = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATA_PATH", "data/alarms.csv"))
    out = Path(sys.argv[2] if len(sys.argv) > 2 else os.getenv("MODEL_PATH", "models/model.json"))
    if not data.exists():
        from .data import make_series
        data.parent.mkdir(parents=True, exist_ok=True)
        make_series().to_csv(data, index=False)
    artifact = train(pd.read_csv(data, parse_dates=["date"]))
    save_atomic(artifact, out)
    print(json.dumps({k: artifact[k] for k in ("model", "backtest_mae", "data_end")}, indent=2))


if __name__ == "__main__":
    main()
