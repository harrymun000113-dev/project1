"""§3.9.0 종합 조언 (Portfolio Recommendation) — Top 20 중 중소기업이 감당 가능한
1~2개국을 우선 추천한다.

실제 LLM 문장 생성은 AI Insight(§3.4)와 마찬가지로 M8-a(데이터 파이프라인 완성 후)에서
붙인다. 그 전까지는 여기서 규칙 기반으로 후보를 고르고 근거 문장도 고정 템플릿으로
채운다 — 단, "규칙 기반"이라고 해서 아무 근거 없이 순위만 나열하지 않고, 실제로
점수 하나만이 아니라 관세·비관세장벽·경쟁 집중도까지 함께 고려해 "감당 가능성"을
계산한다. 인터페이스(`generate(top20) -> dict`)만 고정해 두어, 이후 이 함수 내부만
LLM 연동으로 교체하면 되도록 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

KST = timezone(timedelta(hours=9))

# 점수 대비 감당 가능성 페널티 가중치 — 팀 정책에 맞춰 조정 가능한 기본값.
TARIFF_PENALTY_WEIGHT = 15.0   # 관세율 25%를 만점 페널티로 정규화
NTB_PENALTY_WEIGHT = 10.0      # 비관세 장벽 5건을 만점 페널티로 정규화
CONCENTRATION_PENALTY_WEIGHT = 15.0  # 상위 3개국 점유율 100%를 만점 페널티로 정규화


def _feasibility(row: pd.Series) -> float:
    """단순 `score` 1위가 아니라 '중소기업이 감당하기 쉬운가'를 반영하는 보조 지표.
    관세·비관세장벽·경쟁 집중도가 낮을수록 가점(=페널티가 작음)한다."""
    score = row.get("score")
    score = float(score) if pd.notna(score) else 0.0

    tariff = row.get("tariff_rate_pct")
    tariff_penalty = 0.0 if pd.isna(tariff) else min(float(tariff), 25.0) / 25.0

    ntb_items = row.get("ntb_items")
    ntb_count = len(ntb_items) if isinstance(ntb_items, list) else 0
    ntb_penalty = min(ntb_count, 5) / 5.0

    top3 = row.get("top3_share_pct")
    # 경쟁 정보가 없으면 "모른다"를 유리하게도 불리하게도 취급하지 않도록 중간값(0.5)을 쓴다.
    conc_penalty = 0.5 if pd.isna(top3) else min(float(top3), 100.0) / 100.0

    return score - TARIFF_PENALTY_WEIGHT * tariff_penalty - NTB_PENALTY_WEIGHT * ntb_penalty - CONCENTRATION_PENALTY_WEIGHT * conc_penalty


def _country_label(row: pd.Series, iso3: str) -> str:
    return row.get("name_ko") or row.get("name_en") or iso3


def generate(top20: pd.DataFrame, max_picks: int = 2) -> dict:
    """`top20`(§6 파이프라인 최종 결과, index=iso3)에서 1~2개국을 추천한다."""
    now = datetime.now(KST).isoformat(timespec="seconds")
    if top20.empty:
        return {"recommended_iso3": [], "reason": "분석된 시장이 없어 추천할 수 없습니다.", "generated_at": now}

    feasibility = top20.apply(_feasibility, axis=1)
    ranked = top20.assign(_feasibility=feasibility).sort_values("_feasibility", ascending=False)
    picks = ranked.head(max(1, max_picks))

    parts = []
    for iso3, row in picks.iterrows():
        name = _country_label(row, str(iso3))
        score = row.get("score")
        score_txt = f"{float(score):.1f}점" if pd.notna(score) else "점수 미확인"
        tariff = row.get("tariff_rate_pct")
        tariff_txt = f"관세 {float(tariff):.1f}%" if pd.notna(tariff) else "관세 미확인"
        top3 = row.get("top3_share_pct")
        conc_txt = f"경쟁 집중도 {float(top3):.1f}%" if pd.notna(top3) else "경쟁 정보 미확인"
        parts.append(f"{name}({score_txt}, {tariff_txt}, {conc_txt})")

    top1_iso3 = ranked.index[0]
    is_same_as_score_rank1 = picks.index[0] == top1_iso3 if len(picks) else True
    if is_same_as_score_rank1:
        tail = "점수와 감당 가능성 모두에서 우수해 우선 검토를 추천합니다."
    else:
        tail = "단순 점수 1위보다 관세·비관세장벽·경쟁 집중도가 낮아, 중소기업이 상대적으로 감당하기 쉬운 시장으로 판단됩니다."

    reason = " · ".join(parts) + " 순으로, " + tail

    return {
        "recommended_iso3": [str(iso3) for iso3 in picks.index.tolist()],
        "reason": reason,
        "generated_at": now,
    }
