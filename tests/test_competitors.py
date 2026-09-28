import pandas as pd
import pytest

from blueocean.services import competitors


def test_top3_is_import_share_not_country_count(monkeypatch):
    countries = pd.DataFrame({"name_ko": ["A", "B", "C", "D", "Korea"],
                              "name_en": ["A", "B", "C", "D", "Korea"]},
                             index=["AAA", "BBB", "CCC", "DDD", "KOR"])
    suppliers = pd.DataFrame({"partner_iso3": ["AAA", "BBB", "CCC", "DDD", "KOR", "WLD"],
                              "value": [300, 125.7, 100, 50, 400, 1000]})
    monkeypatch.setattr(competitors, "load_countries", lambda: countries)
    monkeypatch.setattr(competitors.comtrade, "supplier_breakdown", lambda *args: suppliers)
    row = competitors.top3_share("123456", pd.Series({"DEU": 1000}), 2024).loc["DEU"]
    assert row["top3_share_pct"] == pytest.approx(52.57)
    assert [v["iso3"] for v in row["top3"]] == ["AAA", "BBB", "CCC"]
