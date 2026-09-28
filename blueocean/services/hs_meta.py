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


def product_for_hs6(hs6: str) -> dict:
    """HS6 -> 세부 품목명·동의어 (뉴스 검색용). `hs_keyword_map.csv`를 그대로 재사용한다.

    이 CSV에는 한글 동의어 칼럼이 따로 없어 `synonyms_ko`는 항상 빈 목록이다 — 없는
    데이터를 지어내지 않기 위함(§C "가능한 범위에서"). `found=False`면 호출부가 Chapter
    산업군만으로도 검색을 계속할 수 있는 안전한 fallback이다.
    """
    m = _map()
    if hs6 not in m.index:
        return {"found": False, "ko": None, "en": None, "synonyms_ko": [], "synonyms_en": []}

    row = m.loc[hs6]
    ko = (row.get("desc_ko") or "").strip() or None
    en = (row.get("desc_en") or "").strip() or None
    synonyms_en: list[str] = []
    for candidate in (row.get("keyword_en"), row.get("keyword_local")):
        candidate = (candidate or "").strip()
        if candidate and candidate != en and candidate not in synonyms_en:
            synonyms_en.append(candidate)
    return {"found": True, "ko": ko, "en": en, "synonyms_ko": [], "synonyms_en": synonyms_en}


@functools.lru_cache(maxsize=1)
def _chapter_map() -> pd.DataFrame:
    return pd.read_csv(config.HS_CHAPTER_INDUSTRY_CSV, dtype=str).set_index("chapter")


def _split_keywords(raw) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [kw.strip() for kw in raw.split("|") if kw.strip()]


def industry_for_chapter(chapter: str) -> dict:
    """HS Chapter(2자리) -> 산업군 매핑 (HS 2022 체계, `hs_chapter_industry.csv`).

    01~99 전체를 데이터 파일에서 관리한다. Chapter 77은 유보 코드(`reserved=True`),
    98·99는 국가별 특수 용도로 쓰일 수 있어 특정 산업으로 단정하지 않고
    `special=True`로만 표시한다 — 호출부가 이 플래그로 일반 산업군과 구분해 처리할 수
    있다. 데이터에 없는 chapter(정상적으로는 없어야 함)도 예외 대신 안전한 기본값을
    반환한다.
    """
    m = _chapter_map()
    if chapter not in m.index:
        return {
            "chapter": chapter, "industry_ko": "미분류 산업", "industry_en": "Unclassified Industry",
            "keywords_ko": [], "keywords_en": [], "reserved": False, "special": True,
        }
    row = m.loc[chapter]
    return {
        "chapter": chapter,
        "industry_ko": (row.get("industry_ko") or "").strip() or "미분류 산업",
        "industry_en": (row.get("industry_en") or "").strip() or "Unclassified Industry",
        "keywords_ko": _split_keywords(row.get("keywords_ko")),
        "keywords_en": _split_keywords(row.get("keywords_en")),
        "reserved": str(row.get("reserved") or "").strip() == "1",
        "special": str(row.get("special") or "").strip() == "1",
    }
