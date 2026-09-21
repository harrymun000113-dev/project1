"""블루오션 점수(Score) 산정 — 100점 만점 (§4). 이 파일이 유일한 원천(single source of
truth)이다: 점수 계산 · `평가기준(100점)` 모달 · `수식 명세` 모달이 모두 `SCORE_SPEC`을
참조하므로, 배점을 바꿀 일이 있으면 이 파일만 고치면 된다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# key          label               weight column              higher_better transform fixed_range               side
SCORE_SPEC = [
    dict(key="market_size", label="전체 시장 규모", weight=15, column="market_size", higher_is_better=True, transform="log1p", fixed_range=None, side="demand"),
    dict(key="growth_3y", label="최근 3년 성장률", weight=15, column="cagr3_pct", higher_is_better=True, transform=None, fixed_range=(0, 30), side="demand"),
    dict(key="growth_1y", label="최근 1년 성장률", weight=10, column="yoy_pct", higher_is_better=True, transform=None, fixed_range=(0, 30), side="demand"),
    dict(key="trend", label="구글 트렌드", weight=5, column="trend_momentum", higher_is_better=True, transform=None, fixed_range=None, side="demand"),
    dict(key="fx_3y", label="3년 환율 변동", weight=5, column="fx_change_3y_pct", higher_is_better=True, transform=None, fixed_range=None, side="demand"),
    dict(key="korea_share", label="한국 점유율", weight=25, column="korea_share_pct", higher_is_better=False, transform=None, fixed_range=None, side="supply"),
    dict(key="top3_share", label="상위 3개국 점유율", weight=15, column="top3_share_pct", higher_is_better=False, transform=None, fixed_range=None, side="supply"),
    dict(key="tariff", label="관세율", weight=10, column="tariff_rate_pct", higher_is_better=False, transform=None, fixed_range=None, side="supply"),
]
assert sum(s["weight"] for s in SCORE_SPEC) == 100


def normalize(
    s: pd.Series,
    higher_is_better: bool = True,
    transform: str | None = None,
    fixed_range: tuple[float, float] | None = None,
    lo_q: float = 0.05,
    hi_q: float = 0.95,
) -> pd.Series:
    """0~1 정규화. 결측이면 NaN(호출부에서 0.5로 대체)."""
    x = s.astype(float).replace([np.inf, -np.inf], np.nan)

    # (A) 절대평가: lo 이하(역성장 포함) 0점, hi 이상 만점, 사이는 선형. 후보 풀과 무관.
    if fixed_range is not None:
        lo, hi = fixed_range
        n = ((x - lo) / (hi - lo)).clip(0, 1)
        return n if higher_is_better else 1 - n

    # (B) 후보 풀 상대 정규화: min-max + P5~P95 클리핑
    if transform == "log1p":
        x = np.log1p(x.clip(lower=0))
    if x.dropna().empty:
        return pd.Series(np.nan, index=s.index)
    lo, hi = x.quantile(lo_q), x.quantile(hi_q)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return pd.Series(np.nan, index=s.index)  # 분산 0 → 전부 중립
    n = (x.clip(lo, hi) - lo) / (hi - lo)
    return n if higher_is_better else 1 - n


def score(df: pd.DataFrame, keys: list[str] | None = None) -> pd.DataFrame:
    """keys를 주면 해당 항목만으로 계산 후 100점으로 재환산(간이 점수용)."""
    specs = [s for s in SCORE_SPEC if keys is None or s["key"] in keys]
    out = df.copy()
    if out.empty:
        out["score"] = pd.Series(dtype="float64")
        out["potential"] = pd.Series(dtype="float64")
        return out

    for s in specs:
        col = out[s["column"]] if s["column"] in out.columns else pd.Series(np.nan, index=out.index)
        n = normalize(col, s["higher_is_better"], s["transform"], s["fixed_range"])
        out[f"n_{s['key']}"] = n.fillna(0.5)  # 결측/분산 0 → 중립값 0.5
        out[f"pt_{s['key']}"] = out[f"n_{s['key']}"] * s["weight"]

    w_total = sum(s["weight"] for s in specs)
    out["score"] = (out[[f"pt_{s['key']}" for s in specs]].sum(axis=1) / w_total * 100).round(1)

    demand = [s for s in specs if s["side"] == "demand"]
    if demand:
        d_total = sum(s["weight"] for s in demand)
        out["potential"] = (out[[f"pt_{s['key']}" for s in demand]].sum(axis=1) / d_total * 100).round(1)
    else:
        out["potential"] = np.nan
    return out


def score_breakdown(row: pd.Series) -> dict[str, float]:
    """`score_breakdown` 응답 필드용: 항목별 획득 점수(pt_*)만 뽑아 label 없이 key 기준으로."""
    return {s["key"]: round(float(row.get(f"pt_{s['key']}", 0.0)), 1) for s in SCORE_SPEC}
