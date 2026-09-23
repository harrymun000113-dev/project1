"""AI Market Insight generation for the selected country.

Python owns all calculated values. OpenAI only interprets those values and
returns structured Korean copy; missing facts are never filled with guesses.
"""
from __future__ import annotations

import json
import logging

import config
from ..services import openai_client
from ..services.cache import disk_json_cache

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """너는 Blue Ocean Finder의 무역시장 분석 애널리스트다.
한국 중소기업의 수출시장 검토를 돕는 긍정적이지만 신중한 AI Market Insight를 작성한다.

규칙:
1. 반드시 JSON 객체만 반환한다.
2. 입력 JSON의 실제 값만 사실로 사용한다. 숫자를 다시 계산하거나 변경하지 않는다.
3. 국가명, 기업명, 뉴스, 규제, 일정, 출처 URL을 추측하거나 지어내지 않는다.
4. 입력에 검증된 뉴스/출처가 없으면 market_watch의 뉴스 항목과 sources를 빈 배열로 둔다.
5. Blue Ocean Score를 수출 성공확률로 표현하지 않는다.
6. why_this_market은 선정 근거, export_attractiveness는 한국 수출기업 관점의 기회로 구분한다.
7. 중요한 제약은 숨기지 않되, 진출 금지 대신 확인해야 할 변수와 감당 가능성의 톤으로 쓴다.
8. 한국어로 간결하게 쓴다. summary는 2문장, ai_interpretation은 4~6문장이다.
9. why_this_market 최대 3개, export_attractiveness 최대 3개, market_watch 최대 2개다.
"""

_SCHEMA_HINT = {
    "summary": "2문장",
    "why_this_market": [{"title": "string", "metric": "string", "text": "1~2문장", "evidence": ["입력 필드명"]}],
    "export_attractiveness": [{"title": "string", "icon": "string", "text": "2~3줄", "evidence": ["입력 필드명"]}],
    "market_watch": [{"title": "string", "fact": "확인된 사실만", "impact": "한국 수출기업 영향", "source_id": "string 또는 null"}],
    "ai_interpretation": ["문장 4~6개"],
    "key_conclusion": "핵심 결론 1문장",
    "sources": [{"id": "string", "title": "string", "publisher": "string", "date": "string", "url": "string"}],
    "data_confidence": "high|medium|low",
}


def _num(value, digits: int = 2):
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _display(value, unit="", signed=False):
    value = _num(value)
    if value is None:
        return "데이터 없음"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:g}{unit}"


def _facts(hs6: str, row: dict) -> dict:
    growth = row.get("growth") or {}
    return {
        "hs6": hs6,
        "hs_desc": row.get("hs_desc"),
        "iso3": row.get("iso3"),
        "country_name": row.get("name_ko") or row.get("name_en"),
        "rank": row.get("rank"),
        "score": row.get("score"),
        "market_size_usd": row.get("market_size_usd"),
        "cagr3_pct": growth.get("cagr3_pct"),
        "yoy_pct": growth.get("yoy_pct"),
        "korea_share_pct": row.get("korea_share_pct"),
        "korea_world_share_pct": row.get("korea_world_share_pct"),
        "export_gap_pp": row.get("export_gap_pp"),
        "competitors": row.get("competitors"),
        "barriers": row.get("barriers"),
        "fx": row.get("fx"),
        "trend_momentum": row.get("trend_momentum"),
        "score_breakdown": row.get("score_breakdown"),
        "data_flags": row.get("data_flags"),
        "analysis_year": row.get("curr_year"),
        "verified_news": row.get("verified_news") or [],
    }


def _key_indicators(row: dict) -> list[dict]:
    growth = row.get("growth") or {}
    competitors = row.get("competitors") or {}
    return [
        {"key": "market_size_usd", "label": "시장규모", "value": row.get("market_size_usd"), "unit": "USD"},
        {"key": "yoy_pct", "label": "전년 대비 성장률", "value": growth.get("yoy_pct"), "unit": "%", "signed": True},
        {"key": "cagr3_pct", "label": "3년 CAGR", "value": growth.get("cagr3_pct"), "unit": "%", "signed": True},
        {"key": "korea_share_pct", "label": "한국산 점유율", "value": row.get("korea_share_pct"), "unit": "%"},
        {"key": "export_gap_pp", "label": "Export Gap", "value": row.get("export_gap_pp"), "unit": "%p", "signed": True},
        {"key": "top3_share_pct", "label": "경쟁국 Top3 점유율", "value": competitors.get("top3_share_pct"), "unit": "%"},
    ]


def _stub(hs6: str, row: dict) -> dict:
    country = row.get("name_ko") or row.get("name_en") or "선택 국가"
    growth = row.get("growth") or {}
    share = row.get("korea_share_pct")
    gap = row.get("export_gap_pp")
    summary = (
        f"{country}은(는) 시장규모 {_display(row.get('market_size_usd'), ' USD')}와 "
        f"최근 성장률 {_display(growth.get('yoy_pct'), '%', True)}가 확인된 수입시장입니다. "
        f"한국산 점유율 {_display(share, '%')}와 Export Gap {_display(gap, '%p', True)}를 함께 고려하면 추가 시장개척 여지를 검토할 수 있습니다."
    )
    why = []
    if growth.get("yoy_pct") is not None:
        why.append({"title": "수입수요 흐름", "metric": f"전년 대비 {_display(growth.get('yoy_pct'), '%', True)}", "text": "최근 수입수요의 방향을 확인할 수 있는 지표입니다.", "evidence": ["growth.yoy_pct"]})
    if share is not None:
        why.append({"title": "한국산 추가 침투 여지", "metric": f"한국산 점유율 {_display(share, '%')}", "text": "한국산 점유율을 바탕으로 신규 거래처 발굴 가능성을 검토할 수 있습니다.", "evidence": ["korea_share_pct"]})
    if gap is not None:
        why.append({"title": "글로벌 실적 대비 현지 격차", "metric": f"Export Gap {_display(gap, '%p', True)}", "text": "세계시장 실적과 현지 점유율의 차이를 보여주는 참고 지표입니다.", "evidence": ["export_gap_pp"]})
    attractiveness = [
        {"title": "확대되는 수입수요", "icon": "↗", "text": "시장 성장률이 확인된 경우 신규 공급처와 바이어 발굴 기회로 연결해 볼 수 있습니다.", "evidence": ["growth.yoy_pct"]},
        {"title": "낮은 한국산 점유율", "icon": "◎", "text": "현지 점유율이 낮다면 전문 유통사와 신규 거래처를 대상으로 시장개척을 검토할 수 있습니다.", "evidence": ["korea_share_pct"]},
        {"title": "무역환경 확인", "icon": "△", "text": "관세율과 비관세 장벽은 실제 적용 조건을 확인한 뒤 수출전략에 반영해야 합니다.", "evidence": ["barriers"]},
    ]
    barriers = row.get("barriers") or {}
    watch = []
    if barriers.get("tariff_rate_pct") is not None or barriers.get("ntb_count"):
        watch.append({"title": "관세·비관세 장벽", "fact": f"관세율 {_display(barriers.get('tariff_rate_pct'), '%')} / 비관세 장벽 {barriers.get('ntb_count', 0)}건", "impact": "실제 HS 세번과 수입요건을 확인해야 합니다.", "source_id": None})
    if row.get("data_flags"):
        watch.append({"title": "데이터 확인 필요", "fact": "일부 보조지표에 결측 또는 대체 소스 플래그가 있습니다.", "impact": "계약 전 최신 자료로 재검증하는 것이 안전합니다.", "source_id": None})
    interpretation = [summary, "한국산 점유율과 Export Gap은 추가 진입 여지를 판단하는 참고 근거입니다.", "중소기업은 현지 바이어와 유통구조를 확인하면서 소량 테스트로 접근하는 편이 현실적입니다.", "관세와 경쟁국 집중도는 가격·차별화 전략과 함께 검토해야 합니다.", "주요 제약요인은 별도 확인 후 최종 진출 여부를 판단해야 합니다."]
    return {
        "headline": "AI Market Insight", "summary": summary, "key_indicators": _key_indicators(row),
        "why_this_market": why[:3], "export_attractiveness": attractiveness[:3], "market_watch": watch[:2],
        "ai_interpretation": interpretation[:6], "key_conclusion": f"{country}은(는) 시장 기회와 한국산 추가 진입 여지를 함께 확인해 볼 가치가 있는 후보 시장입니다.",
        "sources": [], "data_confidence": "medium" if row.get("data_flags") else "high",
        "footer": {"target": country, "engine": "Predator Engine"},
    }


def _build_user_prompt(hs6: str, row: dict) -> str:
    return "다음 계산 결과만 근거로 Insight를 작성하라. key_indicators의 숫자는 반환하더라도 서버가 Python 값으로 덮어쓴다.\n" + json.dumps({"facts": _facts(hs6, row), "schema": _SCHEMA_HINT}, ensure_ascii=False)


@disk_json_cache(config.CACHE_DIR / "ai_insight", config.TTL_AI_INSIGHT, cache_if=lambda result: result is not None)
def _cached_ai_call(hs6: str, row: dict, _mode: bool, _schema_version: int = 2) -> dict | None:
    if _mode:
        return None
    return openai_client.chat_json(_SYSTEM_PROMPT, _build_user_prompt(hs6, row), temperature=0.35, max_tokens=2200)


def _valid_list(value, limit):
    return value[:limit] if isinstance(value, list) else []


def generate(hs6: str, row: dict) -> dict:
    result = _stub(hs6, row)
    try:
        ai = _cached_ai_call(hs6, row, config.DEMO_OPENAI, 2)
    except Exception as exc:
        log.warning("AI Market Insight generation failed: %s", exc)
        ai = None
    if isinstance(ai, dict):
        for field in ("summary", "key_conclusion", "data_confidence"):
            if isinstance(ai.get(field), str) and ai[field].strip():
                result[field] = ai[field].strip()
        for field, limit in (("why_this_market", 3), ("export_attractiveness", 3), ("market_watch", 2), ("ai_interpretation", 6)):
            values = _valid_list(ai.get(field), limit)
            if values:
                result[field] = values
        if isinstance(ai.get("sources"), list):
            result["sources"] = ai["sources"]
    # 숫자와 Python 계산 결과는 모델 응답으로 덮어쓰지 않는다.
    result["key_indicators"] = _key_indicators(row)
    return result
