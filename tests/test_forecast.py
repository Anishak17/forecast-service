import json

import numpy as np
import pytest

from forecast.data import make_series
from forecast.drift import check_drift
from forecast.models import HoltWinters, SeasonalNaive
from forecast.train import backtest, save_atomic, train


@pytest.fixture(scope="module")
def df():
    return make_series(days=400, seed=1)


def test_seasonal_naive_repeats_last_week():
    y = np.arange(14, dtype=float)
    assert list(SeasonalNaive().fit(y).predict(9)) == [7, 8, 9, 10, 11, 12, 13, 7, 8]


def test_holt_winters_recovers_clean_pattern():
    t = np.arange(84)
    y = 100 + 0.5 * t + np.tile([5, 5, 5, 5, 5, -10, -15], 12)
    pred = HoltWinters(alpha=0.3, beta=0.1, gamma=0.3).fit(y).predict(7)
    t2 = np.arange(84, 91)
    expected = 100 + 0.5 * t2 + np.array([5, 5, 5, 5, 5, -10, -15])
    assert np.max(np.abs(pred - expected)) < 2.0


def test_holt_winters_beats_naive_on_trending_data(df):
    y = df["alarms"].to_numpy()
    assert backtest(HoltWinters, y) < backtest(SeasonalNaive, y)


def test_state_round_trip(df):
    y = df["alarms"].to_numpy()
    m = HoltWinters().fit(y)
    m2 = HoltWinters.from_state(json.loads(json.dumps(m.state())))
    assert np.allclose(m.predict(10), m2.predict(10))


def test_train_artifact(df, tmp_path):
    a = train(df)
    assert a["model"] in a["backtest_mae"] and a["data_end"] == str(df["date"].max().date())
    save_atomic(a, tmp_path / "m" / "model.json")
    assert json.loads((tmp_path / "m" / "model.json").read_text())["model"] == a["model"]


def test_drift_detected_after_level_shift():
    df = make_series(days=400, shift_at=380, shift_size=40, seed=2)
    a = train(df.iloc[:380])
    model = HoltWinters.from_state(a["state"])
    res = check_drift(model.predict(20), df["alarms"].to_numpy()[380:], a["backtest_mae"][a["model"]])
    assert res["drift"]


def test_api(tmp_path, monkeypatch, df):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import forecast.api as api
    path = tmp_path / "model.json"
    monkeypatch.setattr(api, "holder", api.ModelHolder(path))
    client = TestClient(api.app)
    assert client.get("/ready").status_code == 503  # no model yet
    save_atomic(train(df), path)
    assert client.get("/ready").status_code == 200
    r = client.get("/forecast", params={"horizon": 7}).json()
    assert len(r["points"]) == 7
    assert client.get("/forecast", params={"horizon": 500}).status_code == 422
