"""HS6 코드 -> 품목 설명 (`data/hs_keyword_map.csv` 기반, §3.2 헤드라인 품목 라인)."""
from __future__ import annotations

import functools

import pandas as pd

import config


@functools.lru_cache(maxsize=1)
def _map() -> pd.DataFrame:
    return pd.read_csv(config.HS_KEYWORD_MAP_CSV, dtype=str).set_index("hs6")


def describe_hs6(hs6: str) -> str:
    m = _map()
    if hs6 in m.index:
        desc = m.loc[hs6, "desc_en"]
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
    return f"HS {hs6} Product Group"


def describe_hs6_ko(hs6: str) -> str:
    m = _map()
    if hs6 in m.index:
        desc = m.loc[hs6, "desc_ko"]
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
    return f"HS {hs6} 품목군"
