"""HTTP API.

    uvicorn forecast.api:app --port 8000

The model file is re-read when it changes on disk, so a retraining job can swap in a new
model while the API keeps serving (no restart, no downtime).
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .models import MODELS

MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/model.json"))


class ModelHolder:
    def __init__(self, path: Path):
        self.path, self._mtime, self._lock = path, None, Lock()
        self.artifact: dict | None = None
        self.model = None

    def get(self):
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            raise HTTPException(503, "no model trained yet")
        if mtime != self._mtime:
            with self._lock:
                if mtime != self._mtime:
                    artifact = json.loads(self.path.read_text())
                    self.model = MODELS[artifact["model"]].from_state(artifact["state"])
                    self.artifact, self._mtime = artifact, mtime
        return self.model, self.artifact


holder = ModelHolder(MODEL_PATH)
app = FastAPI(title="forecast-service", version="0.1.0")


class Point(BaseModel):
    date: date
    alarms: float


class Forecast(BaseModel):
    model: str
    trained_at: str
    points: list[Point]


@app.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness: a model is loaded, so traffic can be sent here."""
    holder.get()
    return {"status": "ready"}


@app.get("/model")
def model_info() -> dict:
    _, a = holder.get()
    return {k: a[k] for k in ("model", "backtest_mae", "data_end", "trained_at")}


@app.get("/forecast", response_model=Forecast)
def forecast(horizon: int = Query(14, ge=1, le=90)) -> Forecast:
    model, a = holder.get()
    start = date.fromisoformat(a["data_end"]) + timedelta(days=1)
    values = model.predict(horizon)
    return Forecast(model=a["model"], trained_at=a["trained_at"],
                    points=[Point(date=start + timedelta(days=i), alarms=round(float(v), 1))
                            for i, v in enumerate(values)])
