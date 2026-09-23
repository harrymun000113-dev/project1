"""HS 코드 기반 Google News RSS 뉴스 검색.

산업군(Chapter) + 세부 품목(HS6) + 무역 문맥, 세 키워드 그룹을 AND로 묶은 검색식을
만들어 Google News RSS(`https://news.google.com/rss/search`)를 조회한다.

⚠️ Google News RSS는 구글의 공식 개발자 API가 아니다 — 별도 인증 없이 쓸 수 있는 대신,
URL 형식이나 응답 구조가 예고 없이 바뀌거나 요청이 일시적으로 차단될 수 있다(공식
안정성 보장 없음). 그래서:
  - 외부 요청은 항상 타임아웃을 두고 단발로만 시도한다(무한 재시도 금지).
  - 파싱 실패·네트워크 오류는 `NewsUpstreamError`/`NewsParseError`로 구분해 올려
    호출부(API 레이어)가 502로 변환하게 한다 — 이 기능의 장애가 나머지 대시보드를
    막지 않는다.
  - RSS가 주는 HTML/필드는 하나도 신뢰하지 않고 안전하게 벗겨서(`_clean_text`) 쓴다.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import feedparser
import requests
from bs4 import BeautifulSoup

import config
from .cache import disk_json_cache
from .hs_meta import industry_for_chapter, product_for_hs6

log = logging.getLogger(__name__)

NEWS_CACHE_DIR = config.CACHE_DIR / "news"

# ── 검색식 품질 제한 (§D "지나치게 긴 검색식 방지") ─────────────────────────
MAX_KEYWORD_LEN = 40
MAX_INDUSTRY_TERMS = 6
MAX_PRODUCT_TERMS = 8
MAX_QUERY_LEN = 500

TRADE_CONTEXT_KO = ["수출", "수입", "무역", "관세", "통관", "공급망"]
TRADE_CONTEXT_EN = ["export", "import", "trade", "tariff", "customs", "supply chain"]

STRATEGY_PRIMARY = "industry_product_trade"
STRATEGY_FALLBACK = "industry_trade_fallback"


class NewsError(RuntimeError):
    """뉴스 검색 관련 오류의 공통 베이스."""


class NewsUpstreamError(NewsError):
    """Google News RSS 네트워크/HTTP 오류 — 호출부는 502로 변환한다."""


class NewsParseError(NewsError):
    """RSS 응답을 파싱할 수 없음 — 호출부는 502로 변환한다."""


# ── 검색식 생성 (독립적으로 단위 테스트 가능한 순수 함수) ────────────────────
def _clean_keyword(kw: str | None, max_len: int = MAX_KEYWORD_LEN) -> str:
    kw = re.sub(r"\s+", " ", (kw or "").strip())
    return kw[:max_len]


def _dedup_keep_order(items: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        kw = _clean_keyword(raw)
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
    return out


def _or_group(keywords: list[str], max_terms: int) -> str:
    terms = []
    for kw in keywords[:max_terms]:
        terms.append(f'"{kw}"' if " " in kw else kw)
    if not terms:
        return ""
    return terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"


_TRADE_CONTEXT_GROUP = _or_group(_dedup_keep_order(TRADE_CONTEXT_KO + TRADE_CONTEXT_EN), max_terms=99)


def sanitize_extra_keyword(raw: str | None) -> str | None:
    """`product_name` 등 사용자 입력 키워드를 검색식에 넣기 전에 안전하게 정규화한다."""
    if not raw:
        return None
    kw = _clean_keyword(raw, config.NEWS_PRODUCT_NAME_MAX_LEN)
    return kw or None


def hs_expressions(hs6: str) -> list[str]:
    """HS 코드 표현 그룹 — "HS 850440", "HS CODE 850440", "HS 8504", "HS CODE 8504"."""
    heading4 = hs6[:4]
    return [f"HS {hs6}", f"HS CODE {hs6}", f"HS {heading4}", f"HS CODE {heading4}"]


def _cap_query_length(query: str, max_len: int = MAX_QUERY_LEN) -> str:
    return query if len(query) <= max_len else query[:max_len].rsplit(" ", 1)[0]


def build_primary_query(hs6: str, industry: dict, product: dict, extra_keywords: list[str] | None = None) -> dict:
    """산업군 그룹 AND 세부품목 그룹 AND 무역문맥 그룹 (§D 개념 검색식)."""
    industry_keywords = _dedup_keep_order(industry.get("keywords_ko", []) + industry.get("keywords_en", []))
    industry_group = _or_group(industry_keywords, MAX_INDUSTRY_TERMS)

    product_keywords = _dedup_keep_order(
        hs_expressions(hs6)
        + [product.get("ko"), product.get("en")]
        + product.get("synonyms_ko", [])
        + product.get("synonyms_en", [])
        + list(extra_keywords or [])
    )
    product_group = _or_group(product_keywords, MAX_PRODUCT_TERMS)

    parts = [p for p in (industry_group, product_group, _TRADE_CONTEXT_GROUP) if p]
    return {
        "query": _cap_query_length(" AND ".join(parts)),
        "strategy": STRATEGY_PRIMARY,
        "keywords": {"industry": industry_keywords[:MAX_INDUSTRY_TERMS],
                     "product": product_keywords[:MAX_PRODUCT_TERMS],
                     "trade": _dedup_keep_order(TRADE_CONTEXT_KO + TRADE_CONTEXT_EN)},
    }


def build_fallback_query(industry: dict) -> dict:
    """1차 검색 결과가 0건일 때만 쓰는 완화 검색식 — 세부 품목 그룹을 뺀다(§D 품질)."""
    industry_keywords = _dedup_keep_order(industry.get("keywords_ko", []) + industry.get("keywords_en", []))
    industry_group = _or_group(industry_keywords, MAX_INDUSTRY_TERMS)
    parts = [p for p in (industry_group, _TRADE_CONTEXT_GROUP) if p]
    return {
        "query": _cap_query_length(" AND ".join(parts)),
        "strategy": STRATEGY_FALLBACK,
        "keywords": {"industry": industry_keywords[:MAX_INDUSTRY_TERMS], "product": [],
                     "trade": _dedup_keep_order(TRADE_CONTEXT_KO + TRADE_CONTEXT_EN)},
    }


def build_rss_url(query: str, days: int) -> str:
    """Google News RSS 검색 URL. 지역/언어는 한국어 기본값(hl=ko, gl=KR, ceid=KR:ko)."""
    days = max(config.NEWS_DAYS_MIN, min(config.NEWS_DAYS_MAX, days))
    params = {"q": f"{query} when:{days}d", "hl": config.NEWS_HL, "gl": config.NEWS_GL, "ceid": config.NEWS_CEID}
    return f"{config.GOOGLE_NEWS_RSS_URL}?{urlencode(params)}"


# ── RSS 조회·파싱 ────────────────────────────────────────────────────────
def _clean_text(raw: str | None) -> str:
    """RSS 필드에 섞여 올 수 있는 HTML을 벗겨 순수 텍스트만 남긴다(§E, 화면에 HTML 그대로 삽입 금지)."""
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)


def _normalize_title(title: str, source: str | None) -> str:
    """중복 제거용 제목 정규화 — 공백/대소문자, "제목 - 언론사" 접미 표현을 없앤다(§F)."""
    t = title.strip()
    if source and t.endswith(f" - {source}"):
        t = t[: -(len(source) + 3)]
    return re.sub(r"\s+", " ", t).strip().lower()


def _parse_entry(entry) -> dict | None:
    link = getattr(entry, "link", None)
    raw_title = getattr(entry, "title", None)
    if not link or not raw_title:
        return None  # 필수 필드 누락 — 이 기사만 건너뛴다

    source = None
    src = getattr(entry, "source", None)
    if src is not None:
        source = _clean_text(getattr(src, "title", None) or getattr(src, "value", None)) or None

    published_at = None
    published_parsed = getattr(entry, "published_parsed", None)
    if published_parsed:
        try:
            published_at = datetime(*published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            published_at = None

    return {"title": _clean_text(raw_title), "url": link, "source": source, "published_at": published_at}


def _fetch_rss(query: str, days: int) -> list[dict]:
    url = build_rss_url(query, days)
    try:
        resp = requests.get(
            url, timeout=config.NEWS_TIMEOUT_SEC,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BlueOceanFinder/1.0; +news-search)"},
        )
    except requests.RequestException as e:
        raise NewsUpstreamError(f"Google News RSS 요청 실패: {e}") from e

    if resp.status_code >= 400:
        raise NewsUpstreamError(f"Google News RSS 응답 오류: HTTP {resp.status_code}")

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise NewsParseError(f"Google News RSS 파싱 실패: {parsed.get('bozo_exception')}")

    articles = []
    for entry in parsed.entries:
        art = _parse_entry(entry)
        if art:
            articles.append(art)
    return articles


@disk_json_cache(NEWS_CACHE_DIR, config.TTL_NEWS, cache_if=lambda r: isinstance(r, list))
def _fetch_rss_cached(
    hs6: str, chapter: str, extra_keywords: tuple[str, ...], days: int,
    region_lang: str, query_version: int, strategy: str, query: str,
) -> list[dict]:
    """캐시 키 = (hs6, chapter, 추가 키워드, days, 지역/언어, 검색식 버전, 전략, 검색식) 전부 (§G).

    실패(예외)는 이 데코레이터가 절대 캐싱하지 않는다(`cache.py`의 공통 원칙) — 다음
    요청이 바로 재시도할 수 있고, 캐시 장애가 전체 API 장애로 번지지 않는다.
    """
    return _fetch_rss(query, days)


# ── 중복 제거·정렬 (§F) ──────────────────────────────────────────────────
def dedupe_and_sort(articles: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out = []
    for art in articles:
        url = art.get("url")
        if not url:
            continue
        norm_title = _normalize_title(art.get("title", ""), art.get("source"))
        if url in seen_urls or (norm_title and norm_title in seen_titles):
            continue
        seen_urls.add(url)
        if norm_title:
            seen_titles.add(norm_title)
        out.append(art)
    out.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    return out


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ── 오케스트레이션 ───────────────────────────────────────────────────────
def search_news(hs6: str, *, days: int | None = None, limit: int | None = None,
                 product_name: str | None = None) -> dict:
    """HS6 -> Google News 검색 결과 (§H API 응답 스키마와 1:1로 맞춘 dict를 반환).

    호출부(라우트)가 이미 `normalize_hs6_strict`로 hs6 유효성을 검증했다고 가정한다.
    """
    days = _clamp(days if days is not None else config.NEWS_DAYS_DEFAULT, config.NEWS_DAYS_MIN, config.NEWS_DAYS_MAX)
    limit = _clamp(limit if limit is not None else config.NEWS_LIMIT_DEFAULT,
                    config.NEWS_LIMIT_MIN, config.NEWS_LIMIT_MAX)

    chapter = hs6[:2]
    industry = industry_for_chapter(chapter)
    product = product_for_hs6(hs6)
    extra = [k for k in [sanitize_extra_keyword(product_name)] if k]

    region_lang = f"{config.NEWS_GL}:{config.NEWS_HL}"
    primary = build_primary_query(hs6, industry, product, extra_keywords=extra)
    articles = _fetch_rss_cached(
        hs6, chapter, tuple(extra), days, region_lang, config.NEWS_QUERY_VERSION,
        primary["strategy"], primary["query"],
    )
    strategy_used, keywords_used = primary["strategy"], primary["keywords"]

    if not articles:
        # 완화 검색은 1차 결과가 0건일 때만, 그것도 산업군 그룹이 실제로 있을 때만 시도한다
        # (§D "무조건 여러 외부 요청을 발생시키지 않는다").
        fallback = build_fallback_query(industry)
        if fallback["query"] and fallback["query"] != primary["query"]:
            articles = _fetch_rss_cached(
                hs6, chapter, tuple(extra), days, region_lang, config.NEWS_QUERY_VERSION,
                fallback["strategy"], fallback["query"],
            )
            if articles:
                strategy_used, keywords_used = fallback["strategy"], fallback["keywords"]

    deduped = dedupe_and_sort(articles)
    limited = deduped[:limit]

    matched_keywords = (keywords_used["industry"][:2] + keywords_used["product"][:2])[:4] or keywords_used["industry"][:4]
    result_articles = [
        {
            **art,
            "hs_code": hs6,
            "chapter": chapter,
            "industry_ko": industry["industry_ko"],
            "industry_en": industry["industry_en"],
            "product_name": product.get("ko") or product.get("en"),
            "matched_keywords": matched_keywords,
        }
        for art in limited
    ]

    return {
        "hs_code": hs6,
        "chapter": chapter,
        "industry": {"ko": industry["industry_ko"], "en": industry["industry_en"]},
        "product": {"ko": product.get("ko"), "en": product.get("en")},
        "query": {"strategy": strategy_used, "days": days},
        "count": len(result_articles),
        "articles": result_articles,
        # "items"는 "articles"의 별칭이다 — 새 대시보드 디자인의 뉴스 애드온이
        # `d.items || d.news || d` 순으로 읽어서, API 응답 구조를 바꾸지 않고도
        # 그 스크립트를 고치지 않은 채 그대로 붙일 수 있게 한다.
        "items": result_articles,
    }
