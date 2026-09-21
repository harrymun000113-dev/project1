"""KITA 트레이드내비(TradeNavi) — 관세율 · 비관세 장벽 실시간 크롤링 (§5.4).

`config.tradenavi_configured()`가 False인 동안(팀이 실측 XHR 값을 채우기 전)에는
`config.DEMO_TARIFF`가 자동으로 True가 되어 결정론적 합성 데이터를 반환한다 — 그래야
Trade Barriers 카드(§3.5)와 관세율 점수(§4.2 #8)를 처음부터 눈으로 확인할 수 있다.
실측값을 채우고 `BLUEOCEAN_DEMO_MODE`를 auto/0으로 두면 자동으로 실제 크롤러로 전환된다.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

import config
from .cache import disk_json_cache

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

_NTB_POOL = [
    "수입 인증(현지 규격) 요건", "위생·검역(SPS) 서류 요구", "라벨링·현지어 표기 의무",
    "통관 사전신고 절차", "환경 규제(포장재·전자폐기물)", "현지 대리인 지정 의무",
    "쿼터(수량 제한)", "가격 신고 요건",
]


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config.TRADENAVI_REFERER,
    })
    try:
        s.get(config.TRADENAVI_REFERER, timeout=10)  # 세션 쿠키 확보 (필요한 경우)
    except requests.RequestException:
        pass
    return s


def _parse(resp: requests.Response) -> dict:
    """<<실측 후 구현>> 응답(JSON 또는 HTML 조각)에서 아래 세 값만 뽑아 정규화한다.

    tariff_rate_pct : float | None   (한국산 적용세율, 협정세율 우선)
    tariff_type     : "FTA" | "MFN" | ...
    ntb_items       : list[str]      (비관세 장벽 항목명/요약)
    """
    raise NotImplementedError("TradeNavi 실측 응답 포맷 확정 후 구현 (§5.4.2)")


def _fetch_one_live(hs6: str, country_code: str) -> dict:
    if not config.tradenavi_configured():
        return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}

    payload = {k: v.format(hs=hs6, country=country_code)
               for k, v in config.TRADENAVI_PAYLOAD_TEMPLATE.items()}
    session = _new_session()
    for attempt in range(3):
        time.sleep(random.uniform(0.4, 1.2))
        try:
            resp = session.request(config.TRADENAVI_METHOD, config.TRADENAVI_URL, data=payload, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code in (403, 429):
            time.sleep(2 ** (attempt + 1))
            continue
        if resp.ok:
            try:
                return {"ok": True, "fetched_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat(timespec="seconds"),
                        **_parse(resp)}
            except (KeyError, ValueError, NotImplementedError):
                break  # 응답 구조 변경 의심 -> 결측 처리
    return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}


def _fetch_one_demo(hs6: str, country_code: str) -> dict:
    seed = int(hashlib.sha1(f"tariff|{hs6}|{country_code}".encode()).hexdigest(), 16) % (2 ** 32)
    rng = np.random.default_rng(seed)
    has_fta = bool(rng.random() < 0.45)
    rate = float(rng.uniform(0.0, 2.0)) if has_fta else float(rng.uniform(0.0, 25.0))
    n_ntb = int(rng.integers(0, 4))
    ntb_items = list(rng.choice(_NTB_POOL, size=n_ntb, replace=False)) if n_ntb else []
    return {
        "ok": True,
        "fetched_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat(timespec="seconds"),
        "tariff_rate_pct": round(rate, 1),
        "tariff_type": "FTA" if has_fta else "MFN",
        "ntb_items": ntb_items,
    }


@disk_json_cache(config.CACHE_DIR / "tariff", config.TTL_TARIFF, cache_if=lambda r: r.get("ok", False))
def _fetch_one_cached(hs6: str, country_code: str, _mode: bool) -> dict:
    # `_mode`(=config.DEMO_TARIFF)는 캐시 키 전용 — 데모/실제 결과가 섞이지 않게 한다.
    if _mode:
        return _fetch_one_demo(hs6, country_code)
    return _fetch_one_live(hs6, country_code)


def _fetch_one(hs6: str, country_code: str) -> dict:
    return _fetch_one_cached(hs6, country_code, config.DEMO_TARIFF)


def fetch_barriers(hs6: str, cand: pd.DataFrame, workers: int = 4) -> pd.DataFrame:
    """후보국(index=iso3, 컬럼 tradenavi_code 필요) 전체의 관세율·비관세장벽 조회."""

    def _safe_fetch(code: str) -> dict:
        try:
            return _fetch_one(hs6, code)
        except Exception as e:  # 크롤러 예외는 이 국가만 결측 처리 (§6.5)
            log.warning("tariff 조회 예외 (country=%s): %s", code, e)
            return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_safe_fetch, cand["tradenavi_code"]))

    return pd.DataFrame({
        "tariff_rate_pct": [r["tariff_rate_pct"] for r in results],
        "tariff_type": [r["tariff_type"] for r in results],
        "ntb_items": [r["ntb_items"] for r in results],
        "ntb_count": [len(r["ntb_items"] or []) for r in results],
        "tariff_ok": [r["ok"] for r in results],
        "tariff_fetched_at": [r["fetched_at"] for r in results],
    }, index=cand.index)
