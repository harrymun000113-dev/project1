"""Comtrade ④ 처리 — 국가별 Top 3 경쟁국(한국 제외) 점유율 (§3.9.2, §6.3).

`top3_share()` 내부: reporter=<iso>, partner=all, flow=M 호출 → 집계 파트너·
World(0)·KOR 제외 → 금액 상위 3개 → `sum / imp_T × 100` = `top3_share_pct`,
이름·개별 점유율은 `top3` 컬럼(list of dict)에 보관 (경쟁국 팝오버용).
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from . import comtrade
from .countries import load_countries

log = logging.getLogger(__name__)

# 집계 파트너(실제 국가가 아님) — Comtrade가 종종 함께 반환하므로 화이트리스트 밖은 걸러낸다.
_NON_COUNTRY = {"WLD", "W00", "0-WORLD", "NES", "N/A", ""}


def top3_share(hs6: str, market_size: pd.Series, T: int) -> pd.DataFrame:
    """각 타깃국(market_size.index)에 대해 top3_share_pct(합계)와 top3(list[dict])를 계산한다.

    분모는 해당 국가의 `market_size`(= imp_T, Stage 1에서 이미 계산됨)로 고정한다.
    """
    countries = load_countries()
    rows = []
    for iso3, denom in market_size.items():
        try:
            df = comtrade.supplier_breakdown(hs6, iso3, T)
        except Exception as e:  # Comtrade 실패는 이 국가만 결측 처리 (§6.5)
            log.warning("supplier_breakdown 실패 iso3=%s: %s", iso3, e)
            rows.append({"top3_share_pct": float("nan"), "top3": []})
            continue

        if df.empty or denom is None or pd.isna(denom) or denom <= 0:
            rows.append({"top3_share_pct": float("nan"), "top3": []})
            continue

        df = df[df["partner_iso3"].isin(countries.index) & (df["partner_iso3"] != config.KOREA_ISO3)]
        df = df[~df["partner_iso3"].isin(_NON_COUNTRY)]
        agg = df.groupby("partner_iso3")["value"].sum().sort_values(ascending=False)
        top3 = agg.head(3)

        top3_list = [
            {
                "iso3": iso3_s,
                "name_ko": countries.loc[iso3_s, "name_ko"] if iso3_s in countries.index else iso3_s,
                "name_en": countries.loc[iso3_s, "name_en"] if iso3_s in countries.index else iso3_s,
                "share_pct": round(float(v) / denom * 100, 1),
            }
            for iso3_s, v in top3.items()
        ]
        rows.append({
            "top3_share_pct": round(float(top3.sum()) / denom * 100, 2) if len(top3) else float("nan"),
            "top3": top3_list,
        })

    return pd.DataFrame(rows, index=market_size.index)
