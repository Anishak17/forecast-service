"""Synthetic daily series: alarm counts from a telecom network.

trend + weekly pattern (fewer alarms at weekends) + noise, with an optional level shift
partway through to simulate drift (e.g. new equipment rolled out).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_series(days: int = 730, start: str = "2024-01-01", shift_at: int | None = None,
                shift_size: float = 40.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(days)
    weekly = np.array([10, 12, 11, 10, 8, -20, -25], dtype=float)  # Mon..Sun
    dates = pd.date_range(start, periods=days, freq="D")
    y = 200 + 0.05 * t + weekly[dates.dayofweek] + rng.normal(0, 6, days)
    if shift_at is not None:
        y[shift_at:] += shift_size
    return pd.DataFrame({"date": dates, "alarms": np.round(y, 1)})


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/alarms.csv"
    make_series().to_csv(out, index=False)
    print("wrote", out)
