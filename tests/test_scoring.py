import numpy as np
import pandas as pd
import pytest

from blueocean.pipeline.scoring import SCORE_SPEC, normalize, score
from blueocean.services import trends


def test_weights_sum_to_100():
    assert sum(s["weight"] for s in SCORE_SPEC) == 100


@pytest.mark.parametrize(
    "g, expected_n",
    [(-12, 0.0), (0, 0.0), (15, 0.5), (30, 1.0), (48, 1.0)],
)
def test_growth_absolute_scale(g, expected_n):
    s = pd.Series([g])
    n = normalize(s, higher_is_better=True, fixed_range=(0, 30))
    assert n.iloc[0] == pytest.approx(expected_n)


def test_growth_missing_defaults_to_neutral_via_score():
    df = pd.DataFrame({"cagr3_pct": [np.nan], "market_size": [1e8]})
    out = score(df, keys=["growth_3y"])
    assert out["n_growth_3y"].iloc[0] == pytest.approx(0.5)


def test_lower_is_better_direction_is_flipped():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    n_high = normalize(s, higher_is_better=True)
    n_low = normalize(s, higher_is_better=False)
    assert n_low.iloc[0] == pytest.approx(1 - n_high.iloc[0])


def test_zero_variance_column_is_neutral():
    df = pd.DataFrame({"korea_share_pct": [5.0, 5.0, 5.0], "market_size": [1e8, 1e8, 1e8]})
    out = score(df, keys=["korea_share"])
    assert (out["n_korea_share"] == 0.5).all()


def test_score_uses_full_100_when_keys_none():
    df = pd.DataFrame({
        "market_size": [5e8, 1e8, 2e7],
        "cagr3_pct": [10, 5, -2],
        "yoy_pct": [8, 2, -5],
        "trend_momentum": [1.2, 1.0, 0.8],
        "fx_change_3y_pct": [5, 0, -3],
        "korea_share_pct": [1.0, 10.0, 40.0],
        "top3_share_pct": [30.0, 50.0, 70.0],
        "tariff_rate_pct": [0.0, 5.0, 12.0],
    })
    out = score(df)
    assert (out["score"] >= 0).all() and (out["score"] <= 100).all()
    # 한국 점유율이 가장 낮고 성장률이 가장 높은 첫 행이 최고점이어야 한다.
    assert out["score"].idxmax() == 0


def test_score_handles_empty_dataframe():
    df = pd.DataFrame(columns=["market_size", "cagr3_pct"])
    out = score(df)
    assert out.empty
    assert "score" in out.columns


def test_score_missing_column_defaults_neutral_without_crashing():
    df = pd.DataFrame({"market_size": [1e8, 2e8]})  # 나머지 7개 컬럼이 아예 없음
    out = score(df)
    assert len(out) == 2
    assert out["score"].notna().all()


def test_momentum_applies_rate_limit_and_delay(monkeypatch):
    calls = []
    sleep_calls = []

    def fake_fetch(hs6, iso2, mode):
        calls.append((hs6, iso2, mode))
        return 1.0

    monkeypatch.setattr(trends, "_fetch_one_cached", fake_fetch)
    monkeypatch.setattr("blueocean.services.trends.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr("blueocean.services.trends.config.DEMO_SERPAPI", False)
    monkeypatch.setattr("blueocean.services.trends.config.SERPAPI_REQUEST_DELAY_SEC", 0.25)
    monkeypatch.setattr("blueocean.services.trends.config.SERPAPI_MAX_COUNTRIES_PER_RUN", 2)

    series = pd.Series({"USA": "US", "JPN": "JP", "KOR": "KR"})
    result = trends.momentum("330499", series)

    assert list(result.index) == ["USA", "JPN"]
    assert len(calls) == 2
    assert sleep_calls == [0.25]
