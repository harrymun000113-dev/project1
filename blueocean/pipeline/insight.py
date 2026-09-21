"""AI Insight (§3.4) — 콘텐츠·프롬프트는 데이터 파이프라인 완성 후 진행 (v2.4 기준 보류).

지금은 고정 문구를 반환하는 stub이다. 인터페이스(`generate(hs6, row) -> dict`)만 미리
고정해 두어, 이후 실제 LLM 연동 시 이 함수 내부만 교체하면 되도록 한다.
"""
from __future__ import annotations


def generate(hs6: str, row: dict) -> dict:
    name_en = row.get("name_en") or row.get("iso3", "")
    name_ko = row.get("name_ko") or ""
    label = f"{name_en} ({name_ko})" if name_ko else name_en
    return {
        "headline": f"AI Insight — {label}",
        "body": "데이터 분석 중… (AI Insight 생성 로직은 데이터 파이프라인 완성 후 연결됩니다.)",
        "chips": [],
        "action": "",
        "footer": {"target": label, "engine": "Predator Engine"},
    }
