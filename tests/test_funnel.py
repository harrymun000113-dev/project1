import json

import numpy as np
import pandas as pd

import config
from blueocean.pipeline import funnel


def test_pick_base_year_uses_coverage_threshold():
    long_df = pd.DataFrame({
        "period": [2020, 2020, 2021, 2021, 2022],
        "value": [100, 100, 100, 100, 5],  # 2022는 커버리지가 낮음
    })
    assert funnel.pick_base_year(long_df, coverage=0.8) == 2021


def test_pick_base_year_raises_no_data_on_empty_input():
    empty = pd.DataFrame(columns=["period", "value"])
    try:
        funnel.pick_base_year(empty)
        assert False, "NoDataError가 발생해야 한다"
    except funnel.NoDataError:
        pass


def test_stage1_filter_applies_hard_cut_and_gap_filter():
    m = pd.DataFrame({
        "market_size": [config.HARD_CUT_USD - 1, config.HARD_CUT_USD, config.HARD_CUT_USD * 2],
        "export_gap_pp": [10.0, 10.0, -1.0],
    }, index=["A", "B", "C"])
    out = funnel.stage1_filter(m)
    assert list(out.index) == ["B"]  # A는 하드컷 미달, C는 Gap<=0


def test_safe_growth_pct_handles_zero_and_missing_denominator():
    curr = pd.Series([100.0, 50.0, 30.0])
    prev = pd.Series([0.0, np.nan, 10.0])
    out = funnel._safe_growth_pct(curr, prev)
    assert pd.isna(out.iloc[0])
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == 200.0


def test_run_end_to_end_demo_mode_produces_valid_json():
    assert config.DEMO_COMTRADE and config.DEMO_KEXIM and config.DEMO_SERPAPI, "테스트는 데모 모드에서 실행되어야 한다"

    result = funnel.run("854140")

    assert result["meta"]["hs6"] == "854140"
    assert 0 <= result["meta"]["count"] <= config.TOP_N_FINAL
    assert "KOR" not in [row["iso3"] for row in result["top20"]]

    # 하드컷 미만 시장규모는 결과에 없어야 한다.
    for row in result["top20"]:
        assert row["market_size_usd"] is None or row["market_size_usd"] >= config.HARD_CUT_USD

    # NaN이 그대로 새어나가면 json.dumps가 무한값을 문자열 "NaN"으로 뱉는데, 이는 표준 JSON이
    # 아니라 프론트에서 JSON.parse가 깨진다 -> allow_nan=False로 왕복 가능한지 검증한다.
    raw = json.dumps(result, allow_nan=False)
    assert json.loads(raw)["meta"]["hs6"] == "854140"


def test_run_ranks_are_sequential_starting_at_one():
    result = funnel.run("854140")
    ranks = [row["rank"] for row in result["top20"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_run_survives_total_outage_of_one_data_source(monkeypatch):
    """개별 국가가 아니라 서비스 호출 자체가 통째로 죽어도(버그·전면 장애) 다른 7개 채점
    항목과 다른 후보국은 영향받지 않아야 한다 (§5.3.1 "환율 때문에 분석 전체가 중단되는
    일은 없다") — fx 서비스 전체를 강제로 죽여서 run()이 여전히 끝까지 도는지 검증한다."""
    from blueocean.services import fx

    def boom(*args, **kwargs):
        raise RuntimeError("simulated total outage")

    monkeypatch.setattr(fx, "change_3y_krw", boom)
    result = funnel.run("854140")

    assert len(result["top20"]) > 0
    for row in result["top20"]:
        assert row["fx"]["source"] is None
        assert "fx_missing" in row["data_flags"]
        assert row["score"] is not None  # 나머지 7개 항목으로는 정상적으로 점수가 나온다


def test_stage3_full_on_empty_candidates_still_has_score_column():
    """Stage 1이 후보를 0개로 걸러내도 stage3_full은 'score' 컬럼을 반드시 채워야 한다.

    그렇지 않으면 run()의 `full.sort_values("score", ...)`가 KeyError로 죽는다
    (하드컷/Export Gap 필터를 전부 통과하지 못하는 극단적인 HS 코드에서 실제로 발생).
    """
    empty_cand = pd.DataFrame({"market_size": [], "export_gap_pp": []})
    full = funnel.stage3_full(empty_cand, "000000", 2024)
    assert "score" in full.columns
    assert "potential" in full.columns
    assert full.empty
