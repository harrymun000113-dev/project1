import pandas as pd

from blueocean.pipeline import advice


def test_generate_on_empty_top20_returns_no_recommendation():
    result = advice.generate(pd.DataFrame())
    assert result["recommended_iso3"] == []
    assert "추천할 수 없습니다" in result["reason"]
    assert result["generated_at"] is not None


def test_generate_prefers_lower_barriers_over_raw_score_rank1():
    """§3.9.0: 단순 점수 1위가 아니라 관세·비관세장벽·경쟁 집중도까지 고려해야 한다.
    A는 점수가 가장 높지만 관세·비관세장벽·경쟁 집중도가 전부 나쁘고, B는 점수는
    낮지만 세 가지 모두 훨씬 감당하기 쉬우므로 B가 추천 1순위여야 한다."""
    top20 = pd.DataFrame(
        {
            "score": [90.0, 70.0],
            "tariff_rate_pct": [25.0, 0.0],
            "ntb_items": [["a", "b", "c", "d", "e"], []],
            "top3_share_pct": [95.0, 20.0],
            "name_ko": ["A국", "B국"],
            "name_en": ["Country A", "Country B"],
        },
        index=["AAA", "BBB"],
    )
    result = advice.generate(top20, max_picks=2)
    assert result["recommended_iso3"][0] == "BBB"
    assert "B국" in result["reason"]


def test_generate_handles_missing_optional_columns():
    top20 = pd.DataFrame({"score": [80.0, 60.0]}, index=["AAA", "BBB"])
    result = advice.generate(top20, max_picks=1)
    assert result["recommended_iso3"] == ["AAA"]
    assert result["reason"]
