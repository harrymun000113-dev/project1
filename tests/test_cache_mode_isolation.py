"""데모 모드로 캐시된 결과가, 나중에 실제 API 키를 넣은 뒤에도 TTL 만료 전까지 그대로
재사용되는 사고를 막기 위한 회귀 테스트. (실제로 이 문제 때문에 "API 키를 넣었는데도
분석 결과가 여전히 더미 데이터로 보인다"는 증상이 발생했었다.)

각 서비스의 캐시 함수는 `_mode`/`_schema` 인자를 캐시 키의 일부로 받는다 — 이 테스트는
같은 입력이라도 이 값들이 다르면 서로 다른 캐시 항목으로 취급되는지 확인한다.
(`_schema`가 없으면, comtrade.py의 쿼리 로직을 고쳐도 예전 방식으로 받은 캐시가 그대로
재사용되는 사고가 난다 — 실제로 이 문제로 독일 등 일부 국가 수입액이 최대 8배로
부풀려진 캐시가 남아있었다.)
"""
import pandas as pd
import pytest

import config
from blueocean.services import comtrade


def test_imports_cache_key_differs_between_demo_and_real_mode(monkeypatch):
    calls = {"real": 0}

    def fake_call_api(flow, reporter, partner, hs6, periods):
        calls["real"] += 1
        return pd.DataFrame([{"reporter_iso3": "USA", "partner_iso3": "WLD",
                               "period": periods[0], "flow": flow, "value": 999.0}])

    monkeypatch.setattr(comtrade, "_call_api", fake_call_api)

    demo_df = comtrade._imports_cached("999999", "all", 0, (2020,), True, 1)
    assert calls["real"] == 0  # 데모 모드는 실제 API를 호출하지 않는다

    real_df = comtrade._imports_cached("999999", "all", 0, (2020,), False, 1)
    assert calls["real"] == 1  # 같은 인자라도 _mode가 다르면 캐시 미스 -> 실제 호출 발생
    assert real_df.iloc[0]["value"] == 999.0
    assert not demo_df.equals(real_df)

    # 같은 _mode/_schema로 다시 호출하면 캐시가 재사용되어 실제 호출 횟수가 늘지 않는다.
    comtrade._imports_cached("999999", "all", 0, (2020,), False, 1)
    assert calls["real"] == 1

    # _schema가 바뀌면(쿼리 로직을 고친 것) _mode가 같아도 캐시가 무효화되어야 한다.
    comtrade._imports_cached("999999", "all", 0, (2020,), False, 2)
    assert calls["real"] == 2


def test_analyze_cache_key_includes_mode_signature():
    from blueocean.routes.api import _analyze_cache_key

    key_a = _analyze_cache_key("854140")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "MODE_SIGNATURE", "different-mode")
        key_b = _analyze_cache_key("854140")
    assert key_a != key_b
