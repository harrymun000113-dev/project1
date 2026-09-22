"""환율 — 한국수출입은행 오픈 API(주) + yfinance(Fallback) (§5.3).

소스 우선순위: KEXIM(고시 통화) → yfinance(미고시 통화, 또는 KEXIM 전체 실패) → 결측(중립 0.5).
에러는 항상 흡수한다 — 환율 하나 때문에 전체 분석이 죽는 일은 없다 (§5.3.1).

`config.DEMO_KEXIM`이 True(키 미설정 등)이면 두 소스 모두 결정론적 합성 데이터로 대체되어
네트워크 없이도 파이프라인 전체를 끝까지 실행해볼 수 있다. 파싱 로직(`_parse_kexim_rows`)은
데모 여부와 무관하게 동일한 순수 함수라 실제 응답이 오면 그대로 검증 가능하다.
"""
from __future__ import annotations

import hashlib
import logging
import re

import numpy as np
import pandas as pd
import requests

import config
from .cache import ttl_cache

log = logging.getLogger(__name__)

KEXIM_URL = "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
ALIAS = {"CNY": "CNH"}  # 수출입은행은 위안화를 CNH로 고시

# 데모 모드에서 "수출입은행이 고시하는 것으로 취급"할 통화 집합 (실제 고시 목록과 대략 일치).
KEXIM_DEMO_CURRENCIES = {
    "USD", "EUR", "JPY", "GBP", "CNH", "AUD", "CAD", "CHF", "HKD", "SGD",
    "THB", "SEK", "DKK", "NOK", "NZD", "KWD", "SAR", "AED", "QAR", "TWD",
}

# 데모용 대략적인 기준환율(1단위당 KRW). 실측값이 아니라 그럴듯한 크기감만 준다.
_BASE_KRW_PER_UNIT = {
    "USD": 1370.0, "EUR": 1490.0, "JPY": 9.1, "GBP": 1740.0, "CNH": 189.0, "CNY": 189.0,
    "AUD": 890.0, "CAD": 990.0, "CHF": 1560.0, "HKD": 175.0, "SGD": 1010.0, "THB": 38.5,
    "SEK": 128.0, "DKK": 200.0, "NOK": 125.0, "NZD": 820.0, "KWD": 4450.0, "SAR": 365.0,
    "AED": 373.0, "QAR": 376.0, "TWD": 43.0, "INR": 16.4, "BRL": 245.0, "RUB": 14.0,
    "MXN": 73.0, "IDR": 0.086, "TRY": 40.0, "PLN": 345.0, "ARS": 1.4, "ILS": 375.0,
    "MYR": 292.0, "PHP": 23.5, "VND": 0.054, "ZAR": 74.0, "COP": 0.33, "BDT": 11.5,
    "EGP": 27.5, "PKR": 4.9, "CLP": 1.4, "RON": 296.0, "CZK": 58.5, "PEN": 365.0,
    "KZT": 2.6, "DZD": 10.2, "HUF": 3.6, "UAH": 33.0, "MAD": 137.0, "GTQ": 178.0,
    "BGN": 762.0, "OMR": 3560.0, "PAB": 1370.0, "CRC": 2.6, "RSD": 12.8, "NGN": 0.9,
    "IQD": 1.05, "JOD": 1935.0, "TND": 440.0, "BHD": 3640.0, "ISK": 9.9, "KES": 10.6,
    "DOP": 23.0, "LKR": 4.6, "UZS": 0.108, "ETB": 11.0,
}


def _demo_base_rate(currency: str) -> float:
    if currency in _BASE_KRW_PER_UNIT:
        return _BASE_KRW_PER_UNIT[currency]
    seed = int(hashlib.sha1(f"fxbase|{currency}".encode()).hexdigest(), 16) % (2 ** 32)
    return float(np.random.default_rng(seed).uniform(1.0, 500.0))


def _demo_rate_on(currency: str, day: pd.Timestamp) -> float:
    """결정론적 환율: 기준값 + 완만한 장기 드리프트 + 날짜 seed 잡음."""
    base = _demo_base_rate(currency)
    seed = int(hashlib.sha1(f"fxpath|{currency}".encode()).hexdigest(), 16) % (2 ** 32)
    rng = np.random.default_rng(seed)
    drift_annual = float(rng.uniform(-0.025, 0.035))
    years_from_epoch = (day - pd.Timestamp("2020-01-01")).days / 365.25
    trend = (1 + drift_annual) ** years_from_epoch
    day_seed = int(hashlib.sha1(f"fxnoise|{currency}|{day.strftime('%Y%m%d')}".encode()).hexdigest(), 16) % (2 ** 32)
    noise = float(np.random.default_rng(day_seed).normal(1.0, 0.01))
    return base * trend * noise


# ── 파싱 (실측 응답이든 데모든 공용) ─────────────────────────────────────────
def _parse_kexim_rows(rows: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows or []:
        if "cur_unit" not in row:  # 인증 오류 등 결과코드만 온 경우
            continue
        m = re.match(r"([A-Z]+)(?:\((\d+)\))?", row["cur_unit"])  # 'JPY(100)' -> JPY, 100
        if not m:
            continue
        code, unit = m.group(1), int(m.group(2) or 1)
        try:
            out[code] = float(str(row["deal_bas_r"]).replace(",", "")) / unit
        except (ValueError, KeyError):
            continue
    return out


# ── 1) 주 소스: 한국수출입은행 ─────────────────────────────────────────
def _kexim_day_live(yyyymmdd: str) -> dict[str, float]:
    resp = requests.get(KEXIM_URL, timeout=10,
                        params={"authkey": config.KEXIM_API_KEY, "searchdate": yyyymmdd, "data": "AP01"})
    resp.raise_for_status()
    return _parse_kexim_rows(resp.json() or [])


def _kexim_day_demo(yyyymmdd: str) -> dict[str, float]:
    day = pd.Timestamp(yyyymmdd)
    if day.weekday() >= 5:  # 주말은 빈 응답 -> 영업일 보정 로직을 실제로 태운다
        return {}
    return {c: _demo_rate_on(c, day) for c in KEXIM_DEMO_CURRENCIES}


@ttl_cache(ttl=config.TTL_FX, cache_if=lambda r: bool(r))  # 빈 응답(휴일·고시 전)은 캐시하지 않음
def _kexim_day_cached(yyyymmdd: str, _mode: bool) -> dict[str, float]:
    # `_mode`(=config.DEMO_KEXIM)는 캐시 키 전용 — 데모/실제 결과가 섞이지 않게 한다.
    if _mode:
        return _kexim_day_demo(yyyymmdd)
    return _kexim_day_live(yyyymmdd)


def _kexim_day(yyyymmdd: str) -> dict[str, float]:
    return _kexim_day_cached(yyyymmdd, config.DEMO_KEXIM)


def _kexim_on_or_before(day: pd.Timestamp, max_back: int = 7) -> tuple[pd.Timestamp, dict]:
    """해당일 고시가 없으면 직전 영업일로 최대 max_back일 거슬러 올라간다."""
    for k in range(max_back + 1):
        d = day - pd.Timedelta(days=k)
        try:
            rates = _kexim_day(d.strftime("%Y%m%d"))
        except (requests.RequestException, ValueError, KeyError) as e:
            log.warning("KEXIM 조회 실패(%s): %s -> yfinance fallback으로 전환", d.date(), e)
            return day, {}  # 더 거슬러 가도 같은 오류 -> 포기
        if rates:
            return d, rates
    return day, {}


# ── 2) 보조 소스: yfinance (수출입은행 미고시 통화용) ─────────────────────
def _yf_close_live(tickers: list[str], day: pd.Timestamp):
    import yfinance as yf  # 지연 import: fallback이 필요할 때만 로드

    raw = yf.download(tickers, start=day - pd.Timedelta(days=10), end=day + pd.Timedelta(days=1),
                      interval="1d", auto_adjust=False, progress=False)["Close"]
    if isinstance(raw, pd.Series):  # 티커 1개일 때 반환 형식 차이 흡수
        raw = raw.to_frame(tickers[0])
    raw = raw.dropna(how="all")
    if raw.empty:
        return None, {}
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.index[-1], raw.ffill().iloc[-1].dropna().to_dict()


def _yf_two_points_live(ccys: tuple[str, ...], now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    tickers = ["USDKRW=X"] + [f"USD{c}=X" for c in ccys]
    now_d, now = _yf_close_live(tickers, now_day)
    then_d, then = _yf_close_live(tickers, then_day)
    out = {}
    for c in ccys:
        k = f"USD{c}=X"
        if all(x in px for px in (now, then) for x in ("USDKRW=X", k)):
            out[c] = {"now": now["USDKRW=X"] / now[k], "then": then["USDKRW=X"] / then[k],
                      "now_date": now_d, "then_date": then_d}
    return out


def _yf_two_points_demo(ccys: tuple[str, ...], now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    return {
        c: {"now": _demo_rate_on(c, now_day), "then": _demo_rate_on(c, then_day),
            "now_date": now_day, "then_date": then_day}
        for c in ccys
    }


@ttl_cache(ttl=config.TTL_FX, cache_if=lambda r: bool(r))  # 빈 결과는 캐시하지 않음
def _yf_two_points_cached(ccys: tuple[str, ...], now_day: pd.Timestamp, then_day: pd.Timestamp, _mode: bool) -> dict:
    if _mode:
        return _yf_two_points_demo(ccys, now_day, then_day)
    return _yf_two_points_live(ccys, now_day, then_day)


def _yf_two_points(ccys: tuple[str, ...], now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    return _yf_two_points_cached(ccys, now_day, then_day, config.DEMO_KEXIM)


def _fallback(ccys: list[str], now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    if not ccys:
        return {}
    try:
        return _yf_two_points(tuple(sorted(set(ccys))), now_day, then_day)
    except Exception as e:  # yfinance는 429·형식 변경 등 예외 종류가 다양 -> 전부 흡수
        log.warning("yfinance fallback 실패(%s): %s", sorted(set(ccys)), e)
        return {}  # 에러를 던지지 않고 결측(중립 0.5)으로 넘어감


# ── 3) 통합: 통화별로 주 소스 -> 보조 소스 -> 결측 ─────────────────────────
def snapshot() -> dict:
    """오늘과 정확히 3년 전 같은 날짜, 딱 두 시점의 수출입은행 전 통화 환율."""
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    then_target = today - pd.DateOffset(years=3)
    now_d, now = _kexim_on_or_before(today)
    then_d, then = _kexim_on_or_before(then_target)
    return {"today": today, "then_target": then_target,
            "now_date": now_d, "then_date": then_d, "now": now, "then": then}


def latest_usd_krw() -> tuple[float | None, str | None, str | None]:
    """헤더 USD/KRW 토글용: (rate, source, as_of_date). 실패 시 (None, None, None)."""
    snap = snapshot()
    rate = snap["now"].get("USD")
    if rate:
        return float(rate), "KEXIM", snap["now_date"].date().isoformat()
    # KEXIM 실패 -> yfinance로 USDKRW=X 최신 종가 사용 (두 시점 모두 오늘로 조회)
    fb = _fallback(["USD"], snap["today"], snap["today"])
    if "USD" in fb:
        return float(fb["USD"]["now"]), "yfinance", pd.Timestamp(fb["USD"]["now_date"]).date().isoformat()
    return None, None, None


def change_3y_krw(currency_codes: pd.Series) -> pd.DataFrame:
    """후보국 통화코드 Series(index=iso3) -> 3년 환율 변동과 C-5용 값. 점수 항목 5번의 입력."""
    snap = snapshot()

    def has_kexim(c: str) -> bool:
        k = ALIAS.get(c, c)
        return bool(snap["now"].get(k)) and bool(snap["then"].get(k))

    need_fb = [c for c in currency_codes.dropna().unique() if c != "KRW" and not has_kexim(c)]
    fb = _fallback(need_fb, snap["today"], snap["then_target"])  # 미고시 통화만 yfinance (실패해도 예외 없음)

    rows = []
    for ccy in currency_codes:
        n = t = nd = td = src = None
        if pd.notna(ccy) and ccy == "KRW":
            n = t = 1.0
            nd, td, src = snap["today"], snap["then_target"], "KRW"
        elif pd.notna(ccy) and has_kexim(ccy):
            k = ALIAS.get(ccy, ccy)
            n, t, nd, td, src = snap["now"][k], snap["then"][k], snap["now_date"], snap["then_date"], "KEXIM"
        elif ccy in fb:
            f = fb[ccy]
            n, t, nd, td, src = f["now"], f["then"], f["now_date"], f["then_date"], "yfinance"
        ok = bool(n) and bool(t)
        rows.append({
            "fx_change_3y_pct": (n / t - 1) * 100 if ok else float("nan"),
            "krw_per_local_now": n if ok else None,
            "krw_per_local_then": t if ok else None,
            "fx_now_date": nd.date().isoformat() if ok and hasattr(nd, "date") else None,
            "fx_then_date": td.date().isoformat() if ok and hasattr(td, "date") else None,
            "fx_source": src if ok else None,  # "KEXIM" | "yfinance" | "KRW" | None
            "fx_ok": ok,
        })
    return pd.DataFrame(rows, index=currency_codes.index)
