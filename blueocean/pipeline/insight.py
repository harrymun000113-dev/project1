"""AI Insight (§3.4) — 콘텐츠 블록 구조는 v2.5(§3.4.2)로 확정. M8-a(실제 LLM 연동)까지
반영해 `config.OPENAI_API_KEY`가 있으면 OpenAI로 실제 문장을 생성하고, 키가 없거나
호출이 실패하면 고정 문구 stub으로 안전하게 폴백한다 (§6.5와 동일한 "개별 실패가
전체를 막지 않는다" 원칙).

`generate(hs6, row) -> dict` 인터페이스는 그대로 유지한다 — 호출부(`funnel.py`,
`routes/api.py`)는 이 함수가 AI를 쓰는지 stub인지 몰라도 된다.
"""
from __future__ import annotations

import logging

import config
from ..services import openai_client
from ..services.cache import disk_json_cache

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """너는 무역 통계 분석 플랫폼 "Blue Ocean Finder"의 AI 애널리스트다.
한국 중소기업이 해외 신규 수출 시장을 검토할 때 참고할 AI Insight를 작성한다.

반드시 지켜야 할 규칙:
1. 반드시 지정된 JSON 스키마 하나로만 응답한다. 스키마 밖의 텍스트나 설명을 덧붙이지 않는다.
2. why_market은 점수식·정규화 방식·데이터 소스명(예: "UN Comtrade 기준 82점")을 언급하지
   말고, 결과 중심의 쉬운 문장 2~3개로 쓴다.
3. reference(레퍼런스)·contacts(접촉 채널)·gov_programs(정부지원사업)는 확실한 근거가
   없으면 지어내지 말고 exists를 false로 하거나 배열을 비워 둔다. 근거가 약하면
   "~로 추정됩니다" 톤을 쓴다. 실존하지 않는 회사명·사업명·전시회명을 단정적으로
   지어내는 것은 절대 금지한다.
4. risks(리스크)는 규제·물류·대금 리스크를 다루고 항목마다 severity를 "high"/"mid"/"low"
   중 하나로 판정한다. "진출 금지"가 아니라 "감당 가능한 수준"이라는 톤을 유지한다.
5. limitation(한계점)은 데이터·분석 자체의 한계만 한 줄로 쓴다. 실행 관련 리스크는
   risks로 보내고 여기 섞지 않는다.
6. prep_timeline은 구체적인 박람회·행사 일정 근거가 없으면 빈 배열로 둔다.
7. 숫자는 입력으로 주어진 값만 근거로 쓰고, 새로운 수치를 지어내지 않는다.
8. 모든 문장은 한국어로 쓴다."""

_RESPONSE_SCHEMA_HINT = {
    "why_market": "string, 2~3문장",
    "reference": {"exists": True, "examples": ["string"], "reason_if_none": "string 또는 null"},
    "contacts": [{"type": "kotra|association|expo|b2b_platform", "name": "string", "note": "string"}],
    "prep_timeline": [{"milestone": "string", "due": "YYYY-MM-DD 또는 대략적 시기 string"}],
    "risks": [{"category": "regulation|logistics|payment", "severity": "high|mid|low", "note": "string"}],
    "gov_programs": [{"name": "string", "note": "string"}],
    "limitation": "string, 한 줄",
}


def _stub(hs6: str, row: dict) -> dict:
    """키가 없거나 AI 호출이 실패했을 때 쓰는 고정 문구 stub."""
    name_en = row.get("name_en") or row.get("iso3", "")
    name_ko = row.get("name_ko") or ""
    label = f"{name_en} ({name_ko})" if name_ko else name_en
    return {
        "headline": f"AI Insight — {label}",
        "why_market": "데이터 분석 중… (AI Insight 생성 로직은 데이터 파이프라인 완성 후 연결됩니다.)",
        "chips": [],
        "reference": {"exists": None, "examples": [], "reason_if_none": None},
        "contacts": [],
        "prep_timeline": [],
        "risks": [],
        "gov_programs": [],
        "limitation": "",
        "footer": {"target": label, "engine": "Predator Engine"},
    }


def _build_user_prompt(hs6: str, row: dict) -> str:
    import json as _json

    # score_breakdown·data_flags까지 포함해 "실제로 계산된 값"만 모델에 넘긴다 —
    # 모델이 새 수치를 지어낼 필요가 없게 필요한 사실을 전부 쥐여주는 것이 핵심이다.
    facts = {
        "hs6": hs6,
        "country_iso3": row.get("iso3"),
        "country_name_ko": row.get("name_ko"),
        "country_name_en": row.get("name_en"),
        "score": row.get("score"),
        "potential": row.get("potential"),
        "market_size_usd": row.get("market_size_usd"),
        "korea_share_pct": row.get("korea_share_pct"),
        "export_gap_pp": row.get("export_gap_pp"),
        "growth": row.get("growth"),
        "competitors": row.get("competitors"),
        "barriers": row.get("barriers"),
        "fx": row.get("fx"),
        "score_breakdown": row.get("score_breakdown"),
        "data_flags": row.get("data_flags"),
    }
    return (
        "다음은 이 시장에 대해 실제로 계산된 데이터다. 이 값만 근거로 사용하라:\n"
        + _json.dumps(facts, ensure_ascii=False)
        + "\n\n아래 JSON 스키마와 같은 형태로만 응답하라 (값은 예시이며 실제 값으로 채울 것):\n"
        + _json.dumps(_RESPONSE_SCHEMA_HINT, ensure_ascii=False)
    )


@disk_json_cache(config.CACHE_DIR / "ai_insight", config.TTL_AI_INSIGHT, cache_if=lambda r: r is not None)
def _cached_ai_call(hs6: str, row: dict, _mode: bool) -> dict | None:
    # `_mode`(=config.DEMO_OPENAI)는 캐시 키 전용 — 데모/실제 결과가 섞이지 않게 한다.
    if _mode:
        return None
    return openai_client.chat_json(_SYSTEM_PROMPT, _build_user_prompt(hs6, row))


def generate(hs6: str, row: dict) -> dict:
    stub = _stub(hs6, row)

    try:
        ai = _cached_ai_call(hs6, row, config.DEMO_OPENAI)
    except Exception as e:  # AI Insight 실패가 country_detail 응답 전체를 막으면 안 된다 (§6.5)
        log.warning("AI Insight 생성 실패, stub으로 대체 (hs=%s, iso3=%s): %s", hs6, row.get("iso3"), e)
        ai = None

    if not ai:
        return stub

    # response_format=json_object는 "유효한 JSON"만 보장하지, 우리 스키마를 지킨다는
    # 보장은 아니다 (실제로 gov_programs를 reference와 같은 {exists,...} 객체로 잘못
    # 반환하는 사례가 있었다). 필드별 타입이 다르면 그 필드만 무시하고 stub(빈 값)을
    # 유지한다 — 프론트가 타입을 신뢰하고 렌더링할 수 있어야 하므로 여기서 걸러낸다.
    _LIST_FIELDS = ("contacts", "prep_timeline", "risks", "gov_programs")
    merged = dict(stub)
    for key in _LIST_FIELDS:
        value = ai.get(key)
        if isinstance(value, list) and value:
            merged[key] = value
    if isinstance(ai.get("reference"), dict):
        merged["reference"] = ai["reference"]
    if isinstance(ai.get("why_market"), str) and ai["why_market"].strip():
        merged["why_market"] = ai["why_market"]
    if isinstance(ai.get("limitation"), str) and ai["limitation"].strip():
        merged["limitation"] = ai["limitation"]
    return merged
