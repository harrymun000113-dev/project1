import numpy as np
import pandas as pd
import pytest

from blueocean.pipeline.scoring import SCORE_SPEC, flag_growth_outliers, normalize, score


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


# ── §3.9.1 이상치 경고 (규칙 기반) ───────────────────────────────────────
def test_flag_growth_outliers_marks_values_outside_p5_p95():
    # 18개 국가가 전부 10%로 동일하고, 1개국만 500%로 튐 -> 그 1개국만 이상치.
    yoy = [10.0] * 18 + [500.0]
    df = pd.DataFrame({"yoy_pct": yoy, "cagr3_pct": [10.0] * 19})
    out = flag_growth_outliers(df)
    assert out["growth_outlier_yoy"].iloc[-1] == True  # noqa: E712
    assert out["growth_outlier_yoy"].iloc[:-1].sum() == 0
    assert not out["growth_outlier_cagr3"].any()  # 전부 동일값 -> 분산 0 -> 이상치 없음


def test_flag_growth_outliers_missing_column_defaults_to_false():
    df = pd.DataFrame({"market_size": [1e8, 2e8]})  # yoy_pct/cagr3_pct 컬럼 자체가 없음
    out = flag_growth_outliers(df)
    assert not out["growth_outlier_yoy"].any()
    assert not out["growth_outlier_cagr3"].any()


def test_flag_growth_outliers_all_nan_column_defaults_to_false():
    df = pd.DataFrame({"yoy_pct": [np.nan, np.nan, np.nan]})
    out = flag_growth_outliers(df)
    assert not out["growth_outlier_yoy"].any()
