"""SerpAPI Google Trends client — 점수 항목 4번 `trend_momentum` (§5.2)."""
from __future__ import annotations

import hashlib
import logging
import time

import numpy as np
import pandas as pd
import requests

import config
from .cache import disk_json_cache

log = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"
_keyword_map_cache: pd.DataFrame | None = None


def _keyword_map() -> pd.DataFrame:
    global _keyword_map_cache
    if _keyword_map_cache is None:
        _keyword_map_cache = pd.read_csv(config.HS_KEYWORD_MAP_CSV, dtype=str).set_index("hs6")
    return _keyword_map_cache


def _keyword_for(hs6: str) -> str:
    m = _keyword_map()
    if hs6 in m.index:
        kw = m.loc[hs6, "keyword_en"]
        if isinstance(kw, str) and kw.strip():
            return kw.strip()
    return f"HS {hs6}"


def _seed(*parts) -> int:
    raw = "|".join(str(p) for p in parts).encode()
    return int(hashlib.sha1(raw).hexdigest(), 16) % (2 ** 32)


def _demo_momentum(hs6: str, iso2: str) -> float | None:
    if not isinstance(iso2, str) or not iso2:
        return None
    rng = np.random.default_rng(_seed("trend", hs6, iso2))
    # 1.0 근방(정체)을 중심으로 상승/하강 모멘텀을 흩어 놓는다.
    return float(np.clip(rng.normal(1.05, 0.35), 0.1, 3.0))


@disk_json_cache(config.CACHE_DIR / "trends", config.TTL_TRENDS, cache_if=lambda r: r is not None)
def _fetch_one_cached(hs6: str, iso2: str, _mode: bool) -> float | None:
    # `_mode`(=config.DEMO_SERPAPI)는 캐시 키에만 쓰인다 — 데모 캐시와 실제 캐시가
    # 섞이면 안 되기 때문 (comtrade.py의 `_mode` 인자와 같은 이유).
    return _fetch_one(hs6, iso2)


def _fetch_one(hs6: str, iso2: str) -> float | None:
    if config.DEMO_SERPAPI:
        return _demo_momentum(hs6, iso2)

    if not isinstance(iso2, str) or not iso2:
        return None
    try:
        resp = requests.get(SERPAPI_URL, timeout=15, params={
            "engine": "google_trends",
            "q": _keyword_for(hs6),
            "geo": iso2,
            "date": "today 12-m",
            "data_type": "TIMESERIES",
            "api_key": config.SERPAPI_KEY,
        })
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("SerpAPI 트렌드 조회 실패 (hs6=%s, geo=%s): %s", hs6, iso2, e)
        return None

    timeline = payload.get("interest_over_time", {}).get("timeline_data", [])
    if not timeline:
        return None

    values = []
    for point in timeline:
        vals = point.get("values") or []
        if vals and "extracted_value" in vals[0]:
            values.append(float(vals[0]["extracted_value"]))
    if len(values) < 4:  # 최소한의 주간 데이터가 없으면 신뢰 불가
        return None

    recent = values[-13:] if len(values) >= 13 else values
    prior = values[:-13] if len(values) > 13 else values[: max(1, len(values) - len(recent))]
    if not prior:
        return None
    recent_mean, prior_mean = float(np.mean(recent)), float(np.mean(prior))
    if prior_mean <= 0:
        return None
    return recent_mean / prior_mean


def momentum(hs6: str, iso2_series: pd.Series) -> pd.Series:
    """iso3로 인덱싱된 iso2 코드 Series -> trend_momentum Series (실패/결측은 NaN)."""
    items = list(iso2_series.items())
    limit = config.SERPAPI_MAX_COUNTRIES_PER_RUN
    if isinstance(limit, int) and limit > 0 and len(items) > limit:
        log.warning(
            "SerpAPI 후보국 수 %d개가 제한 %d개를 초과해 이번 실행에서는 처음 %d개만 조회합니다.",
            len(items), limit, limit,
        )
        items = items[:limit]

    out = {}
    for i, (iso3, iso2) in enumerate(items):
        if i > 0 and config.SERPAPI_REQUEST_DELAY_SEC > 0:
            time.sleep(config.SERPAPI_REQUEST_DELAY_SEC)
        try:
            out[iso3] = _fetch_one_cached(hs6, iso2, config.DEMO_SERPAPI)
        except Exception as e:  # SerpAPI 한도·형식 변경 등 어떤 예외든 이 국가만 결측 처리
            log.warning("트렌드 조회 예외 (iso3=%s): %s", iso3, e)
            out[iso3] = None
    return pd.Series(out, index=pd.Index([iso3 for iso3, _ in items]), dtype="float64")
