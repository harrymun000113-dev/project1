"""HS 코드 기반 Google News RSS 검색 기능 테스트.

이 파일의 모든 테스트는 실제 Google News 네트워크 호출을 하지 않는다 — RSS
조회 지점(`news._fetch_rss_cached`)을 monkeypatch로 대체하거나, 순수 함수(검색식
생성·중복 제거·RSS 엔트리 파싱)를 직접 호출해서 검증한다.
"""
from __future__ import annotations

import feedparser
import pytest

import config
from blueocean.services import news
from blueocean.services.hs_meta import industry_for_chapter, product_for_hs6
from blueocean.services.news import NewsUpstreamError
from blueocean.utils import hs_chapter, normalize_hs6_strict

# ── A. HS 코드 정규화 및 검증 ────────────────────────────────────────────
def test_normalize_hs6_strict_strips_common_separators():
    assert normalize_hs6_strict("850.440") == "850440"
    assert normalize_hs6_strict("8504-40") == "850440"
    assert normalize_hs6_strict("8504 40") == "850440"
    assert normalize_hs6_strict("  850440  ") == "850440"


def test_normalize_hs6_strict_rejects_wrong_length_or_non_numeric():
    assert normalize_hs6_strict("8504") is None       # 4자리 — 패딩하지 않고 거부
    assert normalize_hs6_strict("85044012") is None   # 8자리 — 절단하지 않고 거부
    assert normalize_hs6_strict("abcdef") is None
    assert normalize_hs6_strict("") is None
    assert normalize_hs6_strict(None) is None


def test_hs_chapter_extracts_first_two_digits():
    assert hs_chapter("854143") == "85"
    assert hs_chapter("300490") == "30"
    assert hs_chapter("870380") == "87"


# ── B. HS Chapter -> 산업군 매핑 ─────────────────────────────────────────
def test_industry_mapping_for_chapter_30_85_87():
    ph = industry_for_chapter("30")
    assert ph["industry_ko"] == "의약품 산업"
    assert ph["industry_en"] == "Pharmaceuticals"

    elec = industry_for_chapter("85")
    assert elec["industry_ko"] == "전기기기·전자제품 산업"
    assert elec["industry_en"] == "Electrical Equipment and Electronics"

    auto = industry_for_chapter("87")
    assert auto["industry_ko"] == "자동차·운송장비 산업"
    assert auto["industry_en"] == "Automotive and Transport Equipment"


def test_chapter_77_is_marked_reserved():
    ch77 = industry_for_chapter("77")
    assert ch77["reserved"] is True
    assert ch77["special"] is False


def test_chapter_98_99_are_special_not_asserted_as_generic_industry():
    for chapter in ("98", "99"):
        info = industry_for_chapter(chapter)
        assert info["special"] is True
        assert info["reserved"] is False


def test_unknown_chapter_falls_back_safely():
    info = industry_for_chapter("00")  # 데이터에 없는 챕터
    assert info["industry_ko"] and info["industry_en"]
    assert info["special"] is True


# ── C. HS6 세부 품목 정보 ────────────────────────────────────────────────
def test_product_for_hs6_known_code_reuses_existing_keyword_map():
    p = product_for_hs6("854143")  # data/hs_keyword_map.csv에 실제로 있는 행
    assert p["found"] is True
    assert p["en"] == "Solar Cells & Modules"


def test_product_for_hs6_unregistered_code_has_safe_fallback():
    p = product_for_hs6("999999")
    assert p["found"] is False
    assert p["ko"] is None and p["en"] is None
    assert p["synonyms_ko"] == [] and p["synonyms_en"] == []
    # Chapter 산업군 매핑 자체는 등록 여부와 무관하게 항상 값을 반환해야 한다.
    assert industry_for_chapter(hs_chapter("999999"))["industry_ko"]


# ── D. 검색식 생성 ───────────────────────────────────────────────────────
def test_build_primary_query_includes_industry_product_and_trade_groups():
    hs6 = "850440"
    industry = industry_for_chapter(hs_chapter(hs6))
    product = product_for_hs6(hs6)
    result = news.build_primary_query(hs6, industry, product)

    assert result["strategy"] == news.STRATEGY_PRIMARY
    query = result["query"]
    assert "HS 850440" in query
    assert "HS CODE 850440" in query
    assert "HS 8504" in query
    assert query.count(" AND ") == 2  # 산업군 / 세부품목 / 무역문맥 3그룹
    # 무역 문맥 키워드가 하나라도 포함되어야 한다.
    assert any(term in query for term in ("export", "수출", "trade", "무역"))


def test_build_primary_query_contains_korean_and_english_keywords():
    hs6 = "300490"
    industry = industry_for_chapter(hs_chapter(hs6))
    product = product_for_hs6(hs6)
    query = news.build_primary_query(hs6, industry, product)["query"]
    assert any("가" <= ch <= "힣" for ch in query)  # 한글 포함
    assert any(ch.isascii() and ch.isalpha() for ch in query)  # 영문 포함


def test_build_primary_query_safe_fallback_for_unregistered_hs6():
    """등록되지 않은 HS6도 Chapter 산업군 + HS 코드 표현만으로 검색식이 만들어져야 한다."""
    hs6 = "999999"
    industry = industry_for_chapter(hs_chapter(hs6))
    product = product_for_hs6(hs6)
    result = news.build_primary_query(hs6, industry, product)
    assert "HS 999999" in result["query"]
    assert result["query"]  # 빈 문자열이 아님


def test_build_fallback_query_drops_product_group():
    industry = industry_for_chapter("85")
    fb = news.build_fallback_query(industry)
    assert fb["strategy"] == news.STRATEGY_FALLBACK
    assert fb["query"].count(" AND ") == 1  # 산업군 / 무역문맥 2그룹뿐


def test_sanitize_extra_keyword_limits_length_and_strips_whitespace():
    long_input = "a" * 500
    cleaned = news.sanitize_extra_keyword(long_input)
    assert len(cleaned) <= config.NEWS_PRODUCT_NAME_MAX_LEN
    assert news.sanitize_extra_keyword("   ") is None
    assert news.sanitize_extra_keyword(None) is None


# ── (내부 헬퍼) days/limit 경계값 ────────────────────────────────────────
def test_clamp_days_and_limit_boundaries():
    assert news._clamp(0, config.NEWS_DAYS_MIN, config.NEWS_DAYS_MAX) == config.NEWS_DAYS_MIN
    assert news._clamp(9999, config.NEWS_DAYS_MIN, config.NEWS_DAYS_MAX) == config.NEWS_DAYS_MAX
    assert news._clamp(config.NEWS_DAYS_DEFAULT, config.NEWS_DAYS_MIN, config.NEWS_DAYS_MAX) == config.NEWS_DAYS_DEFAULT
    assert news._clamp(-5, config.NEWS_LIMIT_MIN, config.NEWS_LIMIT_MAX) == config.NEWS_LIMIT_MIN
    assert news._clamp(500, config.NEWS_LIMIT_MIN, config.NEWS_LIMIT_MAX) == config.NEWS_LIMIT_MAX


# ── E. RSS 조회 및 파싱 ──────────────────────────────────────────────────
_VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News</title>
<item>
<title>&lt;b&gt;태양광 인버터&lt;/b&gt; 수출 급증 - 조선일보</title>
<link>https://news.google.com/rss/articles/abc123?oc=5</link>
<pubDate>Mon, 01 Sep 2025 03:00:00 GMT</pubDate>
<source url="https://chosun.com">조선일보</source>
</item>
</channel></rss>"""

_MISSING_LINK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News</title>
<item><title>링크가 없는 기사</title></item>
</channel></rss>"""


def test_parse_entry_valid_rss_item_strips_html_and_fills_fields():
    feed = feedparser.parse(_VALID_RSS)
    art = news._parse_entry(feed.entries[0])
    assert art is not None
    assert art["url"] == "https://news.google.com/rss/articles/abc123?oc=5"
    assert "<b>" not in art["title"] and "</b>" not in art["title"]
    assert "태양광 인버터" in art["title"]
    assert art["source"] == "조선일보"
    assert art["published_at"] is not None and art["published_at"].startswith("2025-09-01")


def test_parse_entry_missing_required_fields_is_skipped_safely():
    feed = feedparser.parse(_MISSING_LINK_RSS)
    assert news._parse_entry(feed.entries[0]) is None


def test_fetch_rss_network_error_raises_upstream_error(monkeypatch):
    class _FakeSession:
        pass

    def _raise(*a, **k):
        import requests
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(news.requests, "get", _raise)
    with pytest.raises(NewsUpstreamError):
        news._fetch_rss("dummy query", 30)


def test_fetch_rss_bad_status_raises_upstream_error(monkeypatch):
    class _Resp:
        status_code = 503
        content = b""

    monkeypatch.setattr(news.requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(NewsUpstreamError):
        news._fetch_rss("dummy query", 30)


# ── F. 중복 제거와 정렬 ──────────────────────────────────────────────────
def test_dedupe_and_sort_removes_url_and_title_duplicates_and_sorts_desc():
    articles = [
        {"title": "기사 A", "url": "https://n.example/1", "source": None, "published_at": "2025-01-01T00:00:00+00:00"},
        {"title": "기사 A", "url": "https://n.example/1", "source": None, "published_at": "2025-01-01T00:00:00+00:00"},  # 완전 중복
        {"title": "기사 B - 언론사1", "url": "https://n.example/2", "source": "언론사1", "published_at": "2025-03-01T00:00:00+00:00"},
        {"title": "  기사 b  ", "url": "https://n.example/3-tracked", "source": None, "published_at": "2025-02-01T00:00:00+00:00"},  # 제목만 같은 중복(대소문자/공백)
        {"title": "기사 C", "url": "https://n.example/4", "source": None, "published_at": None},
    ]
    out = news.dedupe_and_sort(articles)
    urls = [a["url"] for a in out]
    assert urls.count("https://n.example/1") == 1
    assert "https://n.example/3-tracked" not in urls  # "기사 B"와 정규화 후 같은 제목
    assert urls[0] == "https://n.example/2"  # 최신순 (2025-03) 정렬
    assert urls[-1] == "https://n.example/4"  # published_at 없는 기사는 맨 뒤


# ── H. API ───────────────────────────────────────────────────────────────
def _fake_articles(*urls_and_dates):
    return [
        {"title": f"기사 {i}", "url": url, "source": "테스트언론사", "published_at": dt}
        for i, (url, dt) in enumerate(urls_and_dates)
    ]


def test_api_news_rejects_invalid_hs_code(client):
    resp = client.get("/api/news/hs-code/12ab")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_HS"


def test_api_news_accepts_separators_in_hs_code(client, monkeypatch):
    monkeypatch.setattr(news, "_fetch_rss_cached", lambda *a, **k: [])
    resp = client.get("/api/news/hs-code/850.440")
    assert resp.status_code == 200
    assert resp.get_json()["hs_code"] == "850440"


def test_api_news_success_schema_and_limit(client, monkeypatch):
    def fake_fetch(hs6, chapter, extra, days, region_lang, qv, strategy, query):
        return _fake_articles(
            ("https://n.example/old", "2025-01-01T00:00:00+00:00"),
            ("https://n.example/new", "2025-06-01T00:00:00+00:00"),
        )

    monkeypatch.setattr(news, "_fetch_rss_cached", fake_fetch)
    resp = client.get("/api/news/hs-code/850440?limit=1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["hs_code"] == "850440"
    assert body["chapter"] == "85"
    assert body["industry"]["ko"] and body["industry"]["en"]
    assert body["query"]["strategy"] == news.STRATEGY_PRIMARY
    assert body["query"]["days"] == config.NEWS_DAYS_DEFAULT
    assert body["count"] == 1
    assert len(body["articles"]) == 1
    assert body["articles"][0]["url"] == "https://n.example/new"  # 최신 기사만 남아야 함
    art = body["articles"][0]
    for key in ("title", "url", "source", "published_at", "hs_code", "chapter",
                "industry_ko", "industry_en", "product_name", "matched_keywords"):
        assert key in art


def test_api_news_falls_back_when_primary_strategy_has_no_results(client, monkeypatch):
    def fake_fetch(hs6, chapter, extra, days, region_lang, qv, strategy, query):
        if strategy == news.STRATEGY_PRIMARY:
            return []
        return _fake_articles(("https://n.example/fallback", None))

    monkeypatch.setattr(news, "_fetch_rss_cached", fake_fetch)
    resp = client.get("/api/news/hs-code/300490")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["query"]["strategy"] == news.STRATEGY_FALLBACK
    assert body["count"] == 1


def test_api_news_upstream_failure_returns_502(client, monkeypatch):
    def fake_fetch_raise(*a, **k):
        raise NewsUpstreamError("Google News 응답 오류: HTTP 503")

    monkeypatch.setattr(news, "_fetch_rss_cached", fake_fetch_raise)
    resp = client.get("/api/news/hs-code/870380")
    assert resp.status_code == 502
    assert resp.get_json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_api_news_clamps_out_of_range_days_and_limit(client, monkeypatch):
    captured = {}

    def fake_fetch(hs6, chapter, extra, days, region_lang, qv, strategy, query):
        captured["days"] = days
        return []

    monkeypatch.setattr(news, "_fetch_rss_cached", fake_fetch)
    resp = client.get("/api/news/hs-code/854143?days=9999&limit=0")
    assert resp.status_code == 200
    assert captured["days"] == config.NEWS_DAYS_MAX
    assert resp.get_json()["query"]["days"] == config.NEWS_DAYS_MAX


def test_api_news_query_param_variant_matches_path_variant(client, monkeypatch):
    monkeypatch.setattr(news, "_fetch_rss_cached", lambda *a, **k: [])
    resp = client.get("/api/news?hs=854143")
    assert resp.status_code == 200
    assert resp.get_json()["hs_code"] == "854143"


def test_api_news_response_includes_items_alias_for_articles(client, monkeypatch):
    monkeypatch.setattr(news, "_fetch_rss_cached", lambda *a, **k: _fake_articles(("https://n.example/1", "2025-01-01T00:00:00+00:00")))
    resp = client.get("/api/news/hs-code/854143")
    body = resp.get_json()
    assert body["items"] == body["articles"]


def test_api_news_optional_product_name_is_used_safely(client, monkeypatch):
    captured = {}

    def fake_fetch(hs6, chapter, extra, days, region_lang, qv, strategy, query):
        captured["extra"] = extra
        captured["query"] = query
        return []

    monkeypatch.setattr(news, "_fetch_rss_cached", fake_fetch)
    resp = client.get("/api/news/hs-code/854143?product_name=" + "x" * 500)
    assert resp.status_code == 200
    assert len(captured["extra"][0]) <= config.NEWS_PRODUCT_NAME_MAX_LEN
