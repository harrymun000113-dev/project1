import xml.etree.ElementTree as ET

import pytest
import requests

from blueocean.pipeline import insight
from blueocean.services import precedents


ROW = {"barriers": {"tariff_rate_pct": 0, "ntb_items": ["성분 표시 의무"], "fetched_at": "2026-09-22"},
       "competitors": {"top3_share_pct": 52.57}, "fx": {"change_3y_pct": -7.2}}


def test_watch_keeps_actual_metrics_even_when_ai_returns_unverified_watch(monkeypatch):
    monkeypatch.setattr(insight, "_cached_ai_call", lambda *args: {"market_watch": [{"fact": "made up"}]})
    result = insight.generate("190230", ROW)
    text = str(result["market_watch"])
    for expected in ["0%", "성분 표시 의무", "2026-09-22", "52.57%", "-7.2%"]:
        assert expected in text
    assert "made up" not in text


def test_insight_api_passes_watch_and_current_schema(client, monkeypatch):
    from blueocean.routes import api
    monkeypatch.setattr(api, "_target_row_for_insight", lambda *args: ROW)
    monkeypatch.setattr(insight, "_cached_ai_call", lambda *args: None)
    result = client.get('/api/insight?hs=190230&iso3=SVK').get_json()
    assert result["summary"]
    assert result["ai_interpretation"]
    assert "성분 표시 의무" in result["market_watch"][0]["fact"]
    assert result["market_watch"][0]["impact"]


def rss_response(titles):
    root = ET.Element('rss')
    channel = ET.SubElement(root, 'channel')
    for title in titles:
        item = ET.SubElement(channel, 'item')
        for key, text in {"title": title, "source": "Example News", "link": "https://example.com/news",
                          "pubDate": "Mon, 22 Sep 2025 09:00:00 GMT"}.items():
            ET.SubElement(item, key).text = text
    class Response:
        content = ET.tostring(root, encoding='utf-8')
        def raise_for_status(self):
            pass
    return Response()


def test_precedents_require_country_product_activity_and_source(monkeypatch):
    monkeypatch.setattr(precedents.requests, 'get', lambda *args, **kwargs: rss_response([
        '한국 업체, 슬로바키아 라면 수출 시작', '한국 업체, 프랑스 라면 수출 시작',
        '슬로바키아 자동차 수출 시작', '슬로바키아 라면 가격 동향']))
    result = precedents.search.__wrapped__('190230', 'SVK', '슬로바키아', 'Slovakia')
    assert result['status'] == 'found'
    assert len(result['items']) == 1
    assert result['items'][0]['source'] == 'Example News'
    assert result['items'][0]['evidence_type'] == 'related_news'


def test_precedents_no_matches_is_not_a_connection_error(monkeypatch):
    monkeypatch.setattr(precedents.requests, 'get', lambda *args, **kwargs: rss_response([]))
    assert precedents.search.__wrapped__('190230', 'SVK', '슬로바키아', 'Slovakia')['status'] == 'empty'


def test_precedents_connection_failure_is_not_no_cases(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout()
    monkeypatch.setattr(precedents.requests, 'get', fail)
    with pytest.raises(precedents.PrecedentSearchError):
        precedents.search.__wrapped__('190230', 'SVK', '슬로바키아', 'Slovakia')


def test_precedent_endpoint_validates_and_reports_upstream_errors(client, monkeypatch):
    assert client.get('/api/entry-precedents?hs=bad&iso3=SVK').status_code == 400
    assert client.get('/api/entry-precedents?hs=190230&iso3=ZZZ').status_code == 404
    def fail(*args):
        raise precedents.PrecedentSearchError('temporary failure')
    monkeypatch.setattr(precedents, 'search', fail)
    assert client.get('/api/entry-precedents?hs=190230&iso3=SVK').status_code == 502
