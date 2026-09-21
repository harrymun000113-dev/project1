"""§7.3 `/api/analyze` 응답 스키마 직렬화. pandas/NumPy 값(NaN, np.float64, Timestamp 등)이
표준 JSON(null, float, str)으로 안전하게 바뀌는 유일한 통로로 이 모듈을 둔다 — 그래야
"데이터 처리 중 NaN이 그대로 새어나가 프론트가 깨지는" 부류의 오류를 한 곳에서 막는다.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

import pandas as pd

from ..services.hs_meta import describe_hs6
from .scoring import score_breakdown

KST = timezone(timedelta(hours=9))


def _num(x, ndigits: int | None = None):
    """NaN/None/np.nan -> None. 그 외는 float (선택적으로 반올림)."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, ndigits) if ndigits is not None else f


def _text(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return str(x)


def _growth_direction(yoy_pct) -> str | None:
    n = _num(yoy_pct)
    if n is None:
        return None
    if n > 0:
        return "up"
    if n < 0:
        return "down"
    return "flat"


def _data_flags(row: pd.Series) -> list[str]:
    flags: list[str] = []
    if pd.isna(row.get("cagr3_pct")):
        flags.append("growth3_missing")
    if pd.isna(row.get("yoy_pct")):
        flags.append("growth1_missing")
    if pd.isna(row.get("trend_momentum")):
        flags.append("trend_missing")
    if pd.isna(row.get("top3_share_pct")):
        flags.append("competitors_missing")
    if row.get("fx_source") == "yfinance":
        flags.append("fx_fallback_yfinance")
    if not row.get("fx_ok", False):
        flags.append("fx_missing")
    if not row.get("tariff_ok", False):
        flags.append("tariff_missing")
    return flags


def _row_to_json(row: pd.Series) -> dict:
    top3 = row.get("top3")
    top3_list = top3 if isinstance(top3, list) else []
    ntb_items = row.get("ntb_items")
    ntb_list = ntb_items if isinstance(ntb_items, list) else []

    return {
        "rank": int(row["rank"]),
        "iso3": row.name,
        "iso2": _text(row.get("iso2")),
        "name_ko": _text(row.get("name_ko")),
        "name_en": _text(row.get("name_en")),
        "lat": _num(row.get("lat"), 2),
        "lon": _num(row.get("lon"), 2),
        "score": _num(row.get("score"), 1),
        "potential": _num(row.get("potential"), 1),
        "market_size_usd": _num(row.get("market_size"), 0),
        "korea_share_pct": _num(row.get("korea_share_pct"), 2),
        "export_gap_pp": _num(row.get("export_gap_pp"), 2),
        "growth": {
            "direction": _growth_direction(row.get("yoy_pct")),
            "yoy_pct": _num(row.get("yoy_pct"), 1),
            "cagr3_pct": _num(row.get("cagr3_pct"), 1),
            "prev_year": int(row["prev_year"]) if pd.notna(row.get("prev_year")) else None,
            "prev_value_usd": _num(row.get("prev_value_usd"), 0),
            "curr_year": int(row["curr_year"]) if pd.notna(row.get("curr_year")) else None,
            "curr_value_usd": _num(row.get("curr_value_usd"), 0),
        },
        "competitors": {
            "top3_share_pct": _num(row.get("top3_share_pct"), 1),
            "top3": [
                {
                    "iso3": t.get("iso3"),
                    "name_ko": t.get("name_ko"),
                    "name_en": t.get("name_en"),
                    "share_pct": _num(t.get("share_pct"), 1),
                }
                for t in top3_list
            ],
        },
        "barriers": {
            "tariff_rate_pct": _num(row.get("tariff_rate_pct"), 1),
            "tariff_type": _text(row.get("tariff_type")),
            "ntb_count": len(ntb_list),
            "ntb_items": ntb_list,
            "fetched_at": _text(row.get("tariff_fetched_at")),
        },
        "fx": {
            "currency": _text(row.get("currency_code")),
            "source": _text(row.get("fx_source")),
            "change_3y_pct": _num(row.get("fx_change_3y_pct"), 1),
            "krw_per_local_now": _num(row.get("krw_per_local_now"), 4),
            "krw_per_local_then": _num(row.get("krw_per_local_then"), 4),
            "now_date": _text(row.get("fx_now_date")),
            "then_date": _text(row.get("fx_then_date")),
        },
        "score_breakdown": score_breakdown(row),
        "data_flags": _data_flags(row),
    }


def build_analyze_response(hs6: str, T: int, korea_world_share_pct: float, top20: pd.DataFrame,
                            funnel_counts: dict, world_market_size_usd: float) -> dict:
    hs_desc = describe_hs6(hs6)

    if not top20.empty:
        # 팝오버(§3.9.1)에 필요한 전년도 값도 함께 채워 넣는다.
        prev_col, curr_col = f"imp_{T-1}", f"imp_{T}"
        top20 = top20.assign(
            prev_year=T - 1, curr_year=T,
            prev_value_usd=top20[prev_col] if prev_col in top20.columns else None,
            curr_value_usd=top20[curr_col] if curr_col in top20.columns else None,
        )

    top20_json = [_row_to_json(row) for _, row in top20.iterrows()]

    return {
        "meta": {
            "hs6": hs6,
            "hs_desc": hs_desc,
            "base_year": T,
            "korea_world_share_pct": _num(korea_world_share_pct, 2),
            "count": len(top20_json),
            "funnel": funnel_counts,
            "stale": False,
            "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        },
        "top20": top20_json,
        "world_market_size_usd": _num(world_market_size_usd, 0),
    }
