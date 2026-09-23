"""Loads and caches `data/country_codes.csv`."""
from __future__ import annotations

import functools

import pandas as pd

import config


@functools.lru_cache(maxsize=1)
def load_countries() -> pd.DataFrame:
    """Country reference table indexed by iso3.

    Columns: iso2, comtrade_code, tradenavi_code, name_ko, name_en,
    currency_code, lat, lon.
    """
    df = pd.read_csv(config.COUNTRY_CODES_CSV, dtype={"comtrade_code": "Int64"})
    df = df.set_index("iso3")
    return df


def comtrade_code_to_iso3() -> dict[int, str]:
    df = load_countries()
    return {int(code): iso3 for iso3, code in df["comtrade_code"].dropna().items()}
