"""Two forecasting models, written in NumPy so every step is visible.

SeasonalNaive: tomorrow looks like the same weekday last week. A strong, honest baseline.
HoltWinters:   additive level + trend + weekly season (triple exponential smoothing),
               smoothing parameters chosen by a small grid search on one-step-ahead error.
"""
from __future__ import annotations

import itertools

import numpy as np


class SeasonalNaive:
    name = "seasonal_naive"

    def __init__(self, period: int = 7):
        self.period = period
        self.last: list[float] = []

    def fit(self, y: np.ndarray) -> "SeasonalNaive":
        self.last = [float(v) for v in y[-self.period:]]
        return self

    def predict(self, h: int) -> np.ndarray:
        return np.array([self.last[i % self.period] for i in range(h)])

    def state(self) -> dict:
        return {"period": self.period, "last": self.last}

    @classmethod
    def from_state(cls, s: dict) -> "SeasonalNaive":
        m = cls(s["period"])
        m.last = s["last"]
        return m


class HoltWinters:
    name = "holt_winters"

    def __init__(self, period: int = 7, alpha: float | None = None, beta: float | None = None,
                 gamma: float | None = None):
        self.period = period
        self.params = (alpha, beta, gamma)
        self.level = self.trend = 0.0
        self.season: list[float] = []

    @staticmethod
    def _run(y: np.ndarray, m: int, a: float, b: float, g: float):
        level = float(np.mean(y[:m]))
        trend = float((np.mean(y[m:2 * m]) - np.mean(y[:m])) / m)
        season = list(y[:m] - level)
        sse = 0.0
        for t in range(m, len(y)):
            s = season[t % m]
            pred = level + trend + s
            sse += (y[t] - pred) ** 2
            new_level = a * (y[t] - s) + (1 - a) * (level + trend)
            trend = b * (new_level - level) + (1 - b) * trend
            season[t % m] = g * (y[t] - new_level) + (1 - g) * s
            level = new_level
        return sse, level, trend, season, len(y)

    def fit(self, y: np.ndarray) -> "HoltWinters":
        y = np.asarray(y, dtype=float)
        m = self.period
        if len(y) < 2 * m:
            raise ValueError("need at least two full seasons of data")
        if None in self.params:
            grid = [0.05, 0.1, 0.2, 0.4]
            best = min(itertools.product(grid, [0.01, 0.05, 0.1], grid),
                       key=lambda p: self._run(y, m, *p)[0])
            self.params = best
        _, self.level, self.trend, season, n = self._run(y, m, *self.params)
        # Re-order so season[0] is the weekday right after the last observation.
        self.season = [season[(n + i) % m] for i in range(m)]
        return self

    def predict(self, h: int) -> np.ndarray:
        return np.array([self.level + (i + 1) * self.trend + self.season[i % self.period]
                         for i in range(h)])

    def state(self) -> dict:
        return {"period": self.period, "params": list(self.params), "level": self.level,
                "trend": self.trend, "season": self.season}

    @classmethod
    def from_state(cls, s: dict) -> "HoltWinters":
        m = cls(s["period"], *s["params"])
        m.level, m.trend, m.season = s["level"], s["trend"], s["season"]
        return m


MODELS = {SeasonalNaive.name: SeasonalNaive, HoltWinters.name: HoltWinters}
