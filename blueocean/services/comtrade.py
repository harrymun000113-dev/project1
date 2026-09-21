"""UN Comtrade client (§5.1).

Two modes, chosen by ``config.DEMO_COMTRADE``:

- **Real mode** (an API key is configured): calls the Comtrade API v1
  (``comtradeapi.un.org``), rotating across a pool of subscription keys and
  retrying on 429/quota responses.
- **Demo mode** (no key configured, or ``BLUEOCEAN_DEMO_MODE=1``): returns a
  deterministic synthetic dataset shaped exactly like the real response, so
  the rest of the pipeline (funnel, scoring, API, UI) can be exercised
  end-to-end without credentials. Every value is derived from a seeded RNG
  keyed on (hs6, country, flow) so repeated calls for the same inputs are
  stable — no flicker between requests.

Callers should never need to know which mode is active: both paths return
the same tidy long-format DataFrame with columns
``["reporter_iso3", "partner_iso3", "period", "flow", "value"]``.
"""
from __future__ import annotations

import hashlib
import itertools
import logging
import time
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd
import requests

import config
from .cache import parquet_cache
from .countries import comtrade_code_to_iso3, load_countries

log = logging.getLogger(__name__)

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"


class ComtradeError(RuntimeError):
    """Raised when every configured key/retry has been exhausted."""


# ── key pool rotation ────────────────────────────────────────────────────
_key_cycle = itertools.cycle(config.COMTRADE_API_KEYS) if config.COMTRADE_API_KEYS else None


def _next_key() -> str | None:
    return next(_key_cycle) if _key_cycle else None


def _recent_year_range(n: int = 6, lag: int = 2) -> list[int]:
    """Most recent ``n`` years Comtrade is likely to have data for, given a
    reporting lag of ``lag`` years (annual data typically trails 1-2 years,
    §5.1 주의①)."""
    latest = date.today().year - lag
    return list(range(latest - n + 1, latest + 1))


# ── real HTTP call ───────────────────────────────────────────────────────
def _call_api(flow: str, reporter: str | int, partner: str | int, hs6: str, periods: list[int]) -> pd.DataFrame:
    if not config.COMTRADE_API_KEYS:
        raise ComtradeError("COMTRADE_API_KEYS가 설정되지 않았습니다.")

    # 실측 결과: reporterCode를 생략한 "전체 리포터" 조회는 연도 1개만 물어도 서버에서
    # 40~60초가 걸렸고, 연도를 2~3개 콤마로 묶어서 같이 요청하면 150초를 줘도 계속
    # ReadTimeout이 났다(무료 티어가 그 정도 크기의 계산은 아예 못 끝내는 것으로 보임).
    # 그래서 reporter="all"일 때는 연도별로 쪼개서 한 번에 하나씩 순차 호출한다.
    if reporter == "all" and len(periods) > 1:
        frames = [_call_api(flow, reporter, partner, hs6, [p]) for p in periods]
        non_empty = [f for f in frames if not f.empty]
        return pd.concat(non_empty, ignore_index=True) if non_empty else _tidy([], flow)

    params = {
        "period": ",".join(str(y) for y in periods),
        "cmdCode": hs6,
        "flowCode": flow,
        # 실측 결과, motCode/partner2Code/customsCode를 지정하지 않으면 Comtrade가 운송수단×
        # 2차 파트너×통관절차 전체 조합을 낱개 행으로 돌려준다(국가 하나에 최대 수백 행).
        # 이걸 그대로 sum하면 같은 무역량을 여러 번 겹쳐 세게 된다 — 예: 독일 화장품 수입은
        # 실제 16.1억 달러인데 이 행들을 전부 더하면 128.8억 달러(약 8배)로 계산됐다.
        # motCode=0·partner2Code=0("전체 집계")·customsCode=C00("총계")로 고정해 국가당
        # 정확히 1행(연도당)만 받는다.
        "motCode": "0",
        "partner2Code": "0",
        "customsCode": "C00",
    }
    if reporter != "all":
        params["reporterCode"] = str(reporter)
    if partner != "all":
        params["partnerCode"] = str(partner)

    timeout = 150 if reporter == "all" else 30

    last_exc: Exception | None = None
    attempts = max(3, len(config.COMTRADE_API_KEYS))  # 키가 1개뿐이어도 일시적 오류는 재시도한다
    for attempt in range(attempts):
        key = _next_key()
        try:
            resp = requests.get(
                BASE_URL, params=params, timeout=timeout,
                headers={"Ocp-Apim-Subscription-Key": key},
            )
        except requests.RequestException as e:
            last_exc = e
            log.warning("Comtrade 요청 실패(%d/%d): %s", attempt + 1, attempts, e)
            continue

        if resp.status_code == 429 or resp.status_code == 403:
            log.warning("Comtrade 키 한도 초과(status=%s) — 다음 키로 전환", resp.status_code)
            time.sleep(min(2 ** attempt, 8))
            continue
        try:
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            last_exc = e
            log.warning("Comtrade 응답 처리 실패: %s", e)
            continue

        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        return _tidy(rows, flow)

    raise ComtradeError(f"Comtrade 키 풀 전부 소진: {last_exc}")


def _tidy(rows: list[dict], flow: str) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["reporter_iso3", "partner_iso3", "period", "flow", "value"])
    if not rows:
        return empty

    df = pd.DataFrame(rows)

    def _col(*names: str) -> pd.Series:
        """이름이 바뀌었을 수 있는 실측 응답 필드를 여러 후보로 조회한다.

        후보가 전부 없으면 (엔드포인트/필드명이 문서와 달라졌다는 뜻) None이 아니라
        전부 NaN인 Series를 돌려줘서, 아래 pd.to_numeric·dropna가 안전하게 동작하고
        최종적으로 빈 결과(NO_DATA)로 이어지게 한다 — 여기서 죽으면 분석 전체가 죽는다.
        """
        for name in names:
            if name in df.columns:
                return df[name]
        return pd.Series(np.nan, index=df.index)

    def _resolve_iso3(iso_col: str, code_col: str) -> pd.Series:
        """실측 결과 무료/체험 구독키는 `reporterISO`/`partnerISO`를 전부 null로 주고
        숫자 코드(`reporterCode` 등)만 채워 준다. ISO 문자열이 있으면 그대로 쓰고,
        없으면(또는 컬럼 자체가 없으면) country_codes.csv의 comtrade_code 매핑으로
        숫자 코드를 iso3로 변환한다 — 이걸 안 하면 무료 티어 키에서는 매 응답이
        reporter_iso3=NaN이 되어 전부 dropna로 사라지고 조용히 '데이터 없음'이 된다."""
        iso = _col(iso_col).astype("string")
        has_iso = iso.notna() & (iso.str.len() > 0)
        if has_iso.all():
            return iso
        code_num = pd.to_numeric(_col(code_col), errors="coerce")
        mapped = code_num.map(comtrade_code_to_iso3())
        return iso.where(has_iso, mapped)

    try:
        out = pd.DataFrame({
            "reporter_iso3": _resolve_iso3("reporterISO", "reporterCode"),
            "partner_iso3": _resolve_iso3("partnerISO", "partnerCode"),
            "period": pd.to_numeric(_col("period", "refYear"), errors="coerce").astype("Int64"),
            "flow": flow,
            "value": pd.to_numeric(_col("primaryValue"), errors="coerce"),
        })
    except (TypeError, ValueError) as e:
        log.warning("Comtrade 응답 형식이 예상과 달라 파싱에 실패했습니다: %s", e)
        return empty

    # 집계 파트너(World/Areas nes 등)는 실제 국가가 아니므로 화이트리스트로 걸러야 하지만,
    # 그 필터링은 country_codes.csv 기준으로 pipeline 쪽에서 일괄 처리한다 (§5.1 주의②).
    return out.dropna(subset=["reporter_iso3", "period", "value"])


# ── demo (synthetic) data ─────────────────────────────────────────────────
def _seed(*parts) -> int:
    raw = "|".join(str(p) for p in parts).encode()
    return int(hashlib.sha1(raw).hexdigest(), 16) % (2 ** 32)


def _demo_market_series(hs6: str, iso3: str, years: list[int]) -> dict[int, float]:
    """Deterministic total-import series for one (hs6, country)."""
    rng = np.random.default_rng(_seed("market", hs6, iso3))
    base = float(rng.uniform(5e6, 3e9))
    trend = float(rng.uniform(-0.05, 0.22))  # 연평균 성장/역성장
    noise_scale = rng.uniform(0.03, 0.12)
    out = {}
    years_sorted = sorted(years)
    anchor = years_sorted[-1]
    for y in years_sorted:
        drift = (1 + trend) ** (y - anchor)
        noise = float(rng.normal(1.0, noise_scale))
        out[y] = max(0.0, base * drift * noise)
    return out


def _demo_korea_series(hs6: str, iso3: str, world_series: dict[int, float]) -> dict[int, float]:
    rng = np.random.default_rng(_seed("korea", hs6, iso3))
    share = float(rng.uniform(0.0005, 0.35))
    share_trend = float(rng.uniform(-0.06, 0.10))
    out = {}
    years_sorted = sorted(world_series)
    anchor = years_sorted[-1]
    for y in years_sorted:
        s = max(0.0, min(0.95, share * (1 + share_trend) ** (y - anchor)))
        out[y] = world_series[y] * s
    return out


def _demo_imports(reporter: str | int, partner: int, hs6: str, periods: list[int]) -> pd.DataFrame:
    countries = load_countries()
    if reporter == "all":
        reporters = list(countries.index)
    else:
        code_map = {int(v): k for k, v in countries["comtrade_code"].dropna().items()}
        reporters = [code_map[int(reporter)]] if int(reporter) in code_map else []

    rows = []
    for iso3 in reporters:
        if iso3 == config.KOREA_ISO3:
            continue
        world = _demo_market_series(hs6, iso3, periods)
        if partner == config.KOREA_COMTRADE_CODE:
            series = _demo_korea_series(hs6, iso3, world)
            partner_iso3 = config.KOREA_ISO3
        else:
            series = world
            partner_iso3 = "WLD"
        for y, v in series.items():
            rows.append({"reporter_iso3": iso3, "partner_iso3": partner_iso3, "period": y, "flow": "M", "value": v})
    return pd.DataFrame(rows)


def _demo_exports(reporter: int, partner: int, hs6: str, periods: list[int]) -> pd.DataFrame:
    countries = load_countries()
    code_map = {int(v): k for k, v in countries["comtrade_code"].dropna().items()}
    if reporter == config.KOREA_COMTRADE_CODE:
        # 한국의 세계 수출 = 각국이 한국에서 수입한 값의 합과 개념적으로 동일하게 시뮬레이션
        rows = []
        for iso3 in countries.index:
            if iso3 == config.KOREA_ISO3:
                continue
            world = _demo_market_series(hs6, iso3, periods)
            kor = _demo_korea_series(hs6, iso3, world)
            for y, v in kor.items():
                rows.append({"reporter_iso3": config.KOREA_ISO3, "partner_iso3": "WLD", "period": y, "flow": "X", "value": v})
        df = pd.DataFrame(rows)
        return df.groupby(["reporter_iso3", "partner_iso3", "period", "flow"], as_index=False)["value"].sum()
    if reporter == "all":
        rows = []
        for iso3 in countries.index:
            if iso3 == config.KOREA_ISO3:
                continue
            world = _demo_market_series(hs6, iso3, periods)
            for y, v in world.items():
                # 그 나라의 "총수출"을 총수입과 비례한 규모로 근사 (세계 시장 총량 추정용)
                rows.append({"reporter_iso3": iso3, "partner_iso3": "WLD", "period": y, "flow": "X", "value": v})
        return pd.DataFrame(rows)
    iso3 = code_map.get(int(reporter))
    if iso3 is None:
        return pd.DataFrame(columns=["reporter_iso3", "partner_iso3", "period", "flow", "value"])
    series = _demo_market_series(hs6, iso3, periods)
    return pd.DataFrame([
        {"reporter_iso3": iso3, "partner_iso3": "WLD", "period": y, "flow": "X", "value": v}
        for y, v in series.items()
    ])


def _demo_suppliers(hs6: str, reporter_iso3: str, year: int) -> pd.DataFrame:
    countries = load_countries()
    candidates = [c for c in countries.index if c not in (reporter_iso3, config.KOREA_ISO3)]
    rng = np.random.default_rng(_seed("suppliers", hs6, reporter_iso3, year))
    n = min(len(candidates), int(rng.integers(8, 20)))
    chosen = list(rng.choice(candidates, size=n, replace=False))
    raw = rng.dirichlet(np.ones(n) * 0.6)
    total_import = sum(_demo_market_series(hs6, reporter_iso3, [year]).values())
    rows = [
        {"reporter_iso3": reporter_iso3, "partner_iso3": iso3, "period": year, "flow": "M",
         "value": float(w) * total_import * float(rng.uniform(0.55, 0.95))}
        for iso3, w in zip(chosen, raw)
    ]
    return pd.DataFrame(rows)


# ── public API ────────────────────────────────────────────────────────────
# `years=None`의 실제 의미(_recent_year_range())는 오늘 날짜에 따라 달라지므로, 캐시 키에
# 반드시 "실제로 조회한 연도 목록"이 들어가야 한다. 그래서 연도 해석은 캐시 바깥(이 얇은
# 공개 함수)에서 하고, 캐시가 걸리는 내부 함수는 항상 구체적인 `periods` 튜플만 받는다.
# (연도 해석을 캐시된 함수 안에서 하면, 연말을 넘기고도 예전 연도 범위로 캐시된 결과가
# TTL 만료 전까지 재사용되는 미묘한 버그가 생긴다.)
@parquet_cache(config.CACHE_DIR / "comtrade", config.TTL_COMTRADE)
def _imports_cached(hs6: str, reporter: str | int, partner: int, periods: tuple[int, ...], _mode: bool, _schema: int) -> pd.DataFrame:
    # `_mode`(=config.DEMO_COMTRADE)와 `_schema`(=config.COMTRADE_SCHEMA_VERSION)는 값
    # 자체는 안 쓰지만 캐시 키에 반드시 들어가야 한다. `_mode`가 없으면 데모 모드에서
    # 만든 합성 데이터가 나중에 진짜 API 키를 넣은 뒤에도 TTL이 끝날 때까지 재사용되고,
    # `_schema`가 없으면 쿼리 로직을 고쳐도(§comtrade.py의 motCode/partner2Code/
    # customsCode 필터 추가 등) 예전 방식으로 받은 캐시가 그대로 재사용된다.
    if _mode:
        return _demo_imports(reporter, partner, hs6, list(periods))
    return _call_api("M", reporter, partner, hs6, list(periods))


@parquet_cache(config.CACHE_DIR / "comtrade", config.TTL_COMTRADE)
def _exports_cached(hs6: str, reporter: str | int, partner: int, periods: tuple[int, ...], _mode: bool, _schema: int) -> pd.DataFrame:
    if _mode:
        return _demo_exports(reporter, partner, hs6, list(periods))
    return _call_api("X", reporter, partner, hs6, list(periods))


def imports(hs6: str, reporter: str | int = "all", partner: int = 0, years: Iterable[int] | None = None) -> pd.DataFrame:
    """총수입(reporter가 partner로부터 수입한 값) 원장. flow=M."""
    periods = tuple(years) if years is not None else tuple(_recent_year_range())
    return _imports_cached(hs6, reporter, partner, periods, config.DEMO_COMTRADE, config.COMTRADE_SCHEMA_VERSION)


def exports(hs6: str, reporter: str | int = 410, partner: int = 0, years: Iterable[int] | None = None) -> pd.DataFrame:
    """총수출(reporter가 partner로 수출한 값) 원장. flow=X."""
    periods = tuple(years) if years is not None else tuple(_recent_year_range())
    return _exports_cached(hs6, reporter, partner, periods, config.DEMO_COMTRADE, config.COMTRADE_SCHEMA_VERSION)


@parquet_cache(config.CACHE_DIR / "comtrade", config.TTL_COMTRADE)
def _supplier_breakdown_cached(hs6: str, reporter_iso3: str, year: int, _mode: bool, _schema: int) -> pd.DataFrame:
    if _mode:
        return _demo_suppliers(hs6, reporter_iso3, year)
    countries = load_countries()
    code = countries.loc[reporter_iso3, "comtrade_code"] if reporter_iso3 in countries.index else None
    if code is None or pd.isna(code):
        return pd.DataFrame(columns=["reporter_iso3", "partner_iso3", "period", "flow", "value"])
    return _call_api("M", int(code), "all", hs6, [year])  # partner="all" (전 공급국)


def supplier_breakdown(hs6: str, reporter_iso3: str, year: int) -> pd.DataFrame:
    """공급국별 수입액 (Comtrade ④, §5.1) — reporter=<iso>, partner=all, flow=M, year=T."""
    return _supplier_breakdown_cached(hs6, reporter_iso3, year, config.DEMO_COMTRADE, config.COMTRADE_SCHEMA_VERSION)
