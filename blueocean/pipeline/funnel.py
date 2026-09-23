"""데이터 파이프라인 (§6) — 깔때기 방식.

Stage 0 입력 검증 → Stage 1 벌크 수집(+하드컷·1차 필터) → Stage 2 간이 점수(상위 50)
→ Stage 3 정밀 점수(Top3·트렌드·환율·관세 추가) → Stage 4 정렬 + Top 20.

이 모듈이 원천적으로 마주치는 모든 "데이터가 없거나 이상한" 상황(결측 컬럼, 0으로
나누기, 빈 후보 목록, 전부 NaN인 열 등)은 여기서 흡수한다. 개별 국가의 외부 API 실패는
그 국가만 결측(중립 점수)으로 만들고 파이프라인 자체는 끝까지 실행되어야 한다 (§6.5).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from ..services import comtrade, competitors, fx, tariff, trends
from ..services.countries import load_countries
from .scoring import flag_growth_outliers, score

log = logging.getLogger(__name__)

LITE_KEYS = ["market_size", "growth_3y", "growth_1y", "korea_share"]  # Comtrade 1회 수집으로 계산 가능한 항목


class NoDataError(RuntimeError):
    """해당 HS6에 대해 쓸 만한 데이터가 전혀 없을 때 (§6.5 NO_DATA)."""


def pick_base_year(imports_long: pd.DataFrame, coverage: float = 0.8) -> int:
    """수입액 기준으로 coverage 이상의 국가가 보고한 가장 최근 연도를 T로 사용."""
    if imports_long.empty or "value" not in imports_long.columns:
        raise NoDataError("기준 연도를 정할 수 있는 데이터가 없습니다.")
    by_year = imports_long.groupby("period")["value"].sum()
    by_year = by_year[by_year > 0]
    if by_year.empty:
        raise NoDataError("연도별 수입 데이터가 모두 0입니다.")
    total = by_year.max()
    ok = by_year[by_year >= total * coverage]
    return int(ok.index.max()) if not ok.empty else int(by_year.index.max())


def _pivot(df: pd.DataFrame, prefix: str, years: list[int]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[f"{prefix}_{y}" for y in years])
    p = df.pivot_table(index="reporter_iso3", columns="period", values="value", aggfunc="sum")
    return p.reindex(columns=years).rename(columns=lambda y: f"{prefix}_{y}")


def stage1_market_frame(hs6: str, T: int, countries: pd.DataFrame) -> pd.DataFrame:
    years = [T - 3, T - 1, T]
    world = comtrade.imports(hs6, reporter="all", partner=config.WORLD_COMTRADE_CODE, years=years)
    kor = comtrade.imports(hs6, reporter="all", partner=config.KOREA_COMTRADE_CODE, years=years)

    m = _pivot(world, "imp", years).join(_pivot(kor, "kor", years), how="left")
    for y in years:
        col = f"kor_{y}"
        if col not in m.columns:
            m[col] = 0.0
    m[[f"kor_{y}" for y in years]] = m[[f"kor_{y}" for y in years]].fillna(0)

    m = m[m.index.isin(countries.index)].drop(index=config.KOREA_ISO3, errors="ignore")  # 실제 국가만, 한국 제외
    m = m.join(countries[["iso2", "name_ko", "name_en", "currency_code", "lat", "lon", "tradenavi_code"]])

    for y in years:
        if f"imp_{y}" not in m.columns:
            m[f"imp_{y}"] = np.nan

    m["market_size"] = m[f"imp_{T}"]
    m["yoy_pct"] = _safe_growth_pct(m[f"imp_{T}"], m[f"imp_{T-1}"])
    m["cagr3_pct"] = _safe_cagr_pct(m[f"imp_{T}"], m[f"imp_{T-3}"], years=3)
    m["korea_share_pct"] = _safe_div(m[f"kor_{T}"], m[f"imp_{T}"]) * 100

    kor_exp = comtrade.exports(hs6, reporter=config.KOREA_COMTRADE_CODE, partner=config.WORLD_COMTRADE_CODE, years=[T])["value"].sum()
    world_exp = comtrade.exports(hs6, reporter="all", partner=config.WORLD_COMTRADE_CODE, years=[T])["value"].sum()
    korea_world_share_pct = float(kor_exp / world_exp * 100) if world_exp else float("nan")
    m.attrs["korea_world_share_pct"] = korea_world_share_pct
    m["export_gap_pp"] = korea_world_share_pct - m["korea_share_pct"]

    return m.replace([np.inf, -np.inf], np.nan)


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = a.astype(float) / b.astype(float)
    return out.replace([np.inf, -np.inf], np.nan)


def _safe_growth_pct(curr: pd.Series, prev: pd.Series) -> pd.Series:
    """(curr/prev - 1) * 100, prev<=0이거나 결측이면 NaN (§4.2 #3)."""
    prev_safe = prev.astype(float).where(prev.astype(float) > 0)
    return (_safe_div(curr, prev_safe) - 1) * 100


def _safe_cagr_pct(curr: pd.Series, base: pd.Series, years: int) -> pd.Series:
    """((curr/base)^(1/years) - 1) * 100, base<=0이거나 결측/curr<0이면 NaN (§4.2 #2)."""
    base_safe = base.astype(float).where(base.astype(float) > 0)
    ratio = _safe_div(curr.astype(float).clip(lower=0), base_safe)
    with np.errstate(invalid="ignore"):
        out = (ratio.pow(1 / years) - 1) * 100
    return out


def stage1_filter(m: pd.DataFrame) -> pd.DataFrame:
    """하드컷(1,000만 달러) + 1차 사냥 필터(Export Gap > 0). 사용자가 끌 수 없는 고정 규칙 (§1.1, §6.3)."""
    ok = m["market_size"].notna() & (m["market_size"] >= config.HARD_CUT_USD) & m["export_gap_pp"].notna() & (m["export_gap_pp"] > 0)
    return m[ok].copy()


def stage2_lite(m: pd.DataFrame, top_n: int = config.STAGE2_TOP_N) -> pd.DataFrame:
    if m.empty:
        return m
    lite = score(m, keys=LITE_KEYS)
    return lite.sort_values("score", ascending=False).head(top_n)


def _neutral_top3(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({"top3_share_pct": np.nan, "top3": [[] for _ in index]}, index=index)


def _neutral_trend(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype="float64")


def _neutral_fx(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({
        "fx_change_3y_pct": np.nan, "krw_per_local_now": None, "krw_per_local_then": None,
        "fx_now_date": None, "fx_then_date": None, "fx_source": None, "fx_ok": False,
    }, index=index)


def _neutral_tariff(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({
        "tariff_rate_pct": np.nan, "tariff_type": None, "ntb_items": [[] for _ in index],
        "ntb_count": 0, "tariff_ok": False, "tariff_fetched_at": None,
    }, index=index)


def _enrich(cand: pd.DataFrame, label: str, fetch, fallback) -> pd.DataFrame:
    """Stage 3 보강 항목 하나를 계산한다. 이 서비스 전체가 예기치 않게 죽더라도(개별
    국가 단위가 아니라 호출 자체의 버그·전면 장애) 다른 7개 항목·다른 후보국 채점은
    계속되어야 하므로, 실패 시 해당 항목만 중립값으로 채운 뒤 진행한다 (§5.3.1, §6.5)."""
    try:
        return fetch()
    except Exception as e:
        log.error("%s 보강 단계가 실패해 이 항목은 전부 중립 처리합니다: %s", label, e)
        return fallback(cand.index)


def stage3_full(cand: pd.DataFrame, hs6: str, T: int) -> pd.DataFrame:
    if cand.empty:
        return score(cand)  # 빈 DataFrame이라도 score()를 거쳐야 "score"/"potential" 컬럼이 생긴다

    cand = cand.copy()
    cand = cand.join(_enrich(cand, "경쟁국(Top3)", lambda: competitors.top3_share(hs6, cand["market_size"], T), _neutral_top3))
    cand["trend_momentum"] = _enrich(cand, "구글 트렌드", lambda: trends.momentum(hs6, cand["iso2"]), _neutral_trend)
    cand = cand.join(_enrich(cand, "환율", lambda: fx.change_3y_krw(cand["currency_code"]), _neutral_fx))
    cand = cand.join(_enrich(cand, "관세율·비관세장벽", lambda: tariff.fetch_barriers(hs6, cand), _neutral_tariff))
    return score(cand)  # 8개 항목 100점


def run(hs6: str) -> dict:
    """전체 깔때기를 실행하고 §7.3 스키마의 dict를 반환한다."""
    countries = load_countries()

    world_long = comtrade.imports(hs6, reporter="all", partner=config.WORLD_COMTRADE_CODE, years=None)
    T = pick_base_year(world_long)

    m_all = stage1_market_frame(hs6, T, countries)
    stage1_total = len(m_all)
    m = stage1_filter(m_all)
    stage1_kept = len(m)

    cand = stage2_lite(m, top_n=config.STAGE2_TOP_N)
    # §3.9.1 이상치 경고: 후보 풀(Stage 2, 상위 50개국) 기준으로 판정해야 하므로
    # Stage 3(관세·트렌드·환율 보강)로 넘어가기 전, 이 시점의 yoy_pct/cagr3_pct로 계산한다.
    cand = flag_growth_outliers(cand)
    stage2_kept = len(cand)

    full = stage3_full(cand, hs6, T)
    top20 = full.sort_values("score", ascending=False).head(config.TOP_N_FINAL).copy()
    top20["rank"] = range(1, len(top20) + 1)

    korea_world_share_pct = m_all.attrs.get("korea_world_share_pct", float("nan"))

    from . import advice, respond

    return respond.build_analyze_response(
        hs6=hs6, T=T, korea_world_share_pct=korea_world_share_pct, top20=top20,
        funnel_counts={"stage1": stage1_total if stage1_total else stage1_kept,
                       "stage2": stage2_kept, "stage3": len(top20)},
        world_market_size_usd=float(m_all["market_size"].sum(skipna=True)) if not m_all.empty else 0.0,
        portfolio_advice=advice.generate(top20),  # §3.9.0
    )


def country_detail(hs6: str, iso3: str, T: int) -> dict:
    """`/api/country/<iso3>/detail` — C-4 갭 추이(§3.8) + AI Insight(§3.4) 재료."""
    countries = load_countries()
    if iso3 not in countries.index:
        raise NoDataError(f"알 수 없는 국가 코드: {iso3}")

    code = countries.loc[iso3, "comtrade_code"]
    if pd.isna(code):
        raise NoDataError(f"{iso3}의 Comtrade 코드가 없습니다")
    reporter = int(code)

    years = [y for y in config.COMTRADE_YEARS if y <= T] or [T]
    # 이 화면은 선택한 국가 "하나"만 보여주므로 reporter=all(전세계 197개국 전체 조회)이
    # 아니라 그 나라 코드로만 조회한다. reporter=all은 10개 연도를 쪼개 순차 호출해야
    # 해서(§comtrade.py) 국가 하나 보자고 수십~수백 초짜리 호출을 반복하게 되고, 실제로
    # 이것 때문에 API 할당량이 빠듯한 환경에서 이 그래프만 유독 실패하는 문제가 있었다.
    world = comtrade.imports(hs6, reporter=reporter, partner=config.WORLD_COMTRADE_CODE, years=years)
    kor = comtrade.imports(hs6, reporter=reporter, partner=config.KOREA_COMTRADE_CODE, years=years)
    kor_exp_long = comtrade.exports(hs6, reporter=config.KOREA_COMTRADE_CODE, partner=config.WORLD_COMTRADE_CODE, years=years)
    world_exp_long = comtrade.exports(hs6, reporter="all", partner=config.WORLD_COMTRADE_CODE, years=years)

    w = world.groupby("period")["value"].sum()
    k = kor.groupby("period")["value"].sum()
    kx = kor_exp_long.groupby("period")["value"].sum()
    wx = world_exp_long.groupby("period")["value"].sum()

    gap_trend = []
    for y in years:
        total_import = float(w.get(y, 0.0))
        korea_export = float(k.get(y, 0.0))
        kor_world_share = float(kx.get(y, 0.0)) / float(wx.get(y, 0.0)) * 100 if wx.get(y, 0.0) else None
        korea_share = korea_export / total_import * 100 if total_import else None
        gap = (kor_world_share - korea_share) if (kor_world_share is not None and korea_share is not None) else None
        gap_trend.append({
            "year": y,
            "total_import_usd": round(total_import, 2),
            "korea_export_usd": round(korea_export, 2),
            "export_gap_pp": round(gap, 2) if gap is not None else None,
        })

    # AI Insight(§3.4)는 여기서 만들지 않는다 — 이 함수가 아는 것은 gap_trend 뿐이라
    # score/growth/관세/경쟁국처럼 AI가 근거로 삼을 실제 계산값이 없다. 그 값들은 이미
    # `/api/analyze` 캐시에 있으므로, routes/api.py의 country_detail 뷰가 그 캐시된
    # top20 행을 찾아 insight.generate()에 넘긴다 (없으면 최소 정보로 폴백).
    return {"gap_trend": gap_trend}
