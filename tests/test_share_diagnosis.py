import copy
import time

import pytest

import config
from blueocean.pipeline import share_diagnosis as diagnosis


@pytest.fixture
def row():
    return {"iso3": "ESP", "iso2": "ES", "reporter_code": 724, "name_ko": "스페인", "base_year": 2024,
            "generated_at": "2026-09-28T00:00:00+00:00", "market_size_usd": 200000000, "korea_import_usd": 1000000,
            "korea_share_pct": .5, "competitors": {"top3_share_pct": 75, "top3": [
                {"iso3": "ITA", "name_ko": "이탈리아", "share_pct": 40},
                {"iso3": "FRA", "name_ko": "프랑스", "share_pct": 20},
                {"iso3": "DEU", "name_ko": "독일", "share_pct": 15}]},
            "korea_import_history": [{"year": 2021, "total_import_usd": 100000000, "korea_import_usd": 1000000},
                                     {"year": 2024, "total_import_usd": 200000000, "korea_import_usd": 1000000}],
            "barriers": {"tariff_rate_pct": 0, "tariff_type": "FTA", "ntb_items": ["표시 요건"], "fetched_at": "2026-09-22"}}


def test_facts_use_named_suppliers_actual_growth_and_rule_out_zero_tariff(row):
    result = diagnosis.build('190230', row)
    facts = {f['id']: f for f in result['facts']}
    assert '이탈리아 40%' in facts['F2']['observation']
    assert '1%→0.5%' in facts['F3']['observation']
    assert '따라가지 못해' in facts['F3']['interpretation']
    assert '관세율은 0%' in facts['F4']['interpretation']
    sources = {s['id']: s for s in result['sources']}
    for fact in result['facts']:
        assert all(sid in sources for sid in fact['source_ids'])
    assert 'reporterCode=724' in sources['S2']['query_url']
    assert 'partnerCode=410' in sources['S2']['query_url']
    assert 'cmdCode=190230' in sources['S2']['query_url']
    assert '2021%2C2024' in sources['S5']['query_url']


def test_increasing_share_is_not_described_as_declining(row):
    row['korea_import_history'][-1]['korea_import_usd'] = 4000000
    fact = next(f for f in diagnosis.build('190230', row)['facts'] if f['id'] == 'F3')
    assert '상승했습니다' in fact['interpretation']


def test_missing_history_does_not_become_zero_imports(row):
    row['korea_import_history'][0]['korea_import_usd'] = None
    assert all(f['id'] != 'F3' for f in diagnosis.build('190230', row)['facts'])


def test_demo_data_never_claims_actual_causal_analysis(row, monkeypatch):
    monkeypatch.setattr(config, 'DEMO_COMTRADE', True)
    result = diagnosis.generate('190230', row)
    assert result['mode'] == 'demo'
    assert result['ai'] is None
    assert result['facts'] == []
    assert result['external_research']['status'] == 'disabled'


def test_external_research_preserves_sources_and_omits_opinions(row, monkeypatch):
    monkeypatch.setattr(config, 'DEMO_COMTRADE', False)
    external = {'status': 'ok', 'facts': [{'text': '검증된 원문 요약', 'sources': [{'url': 'https://www.wto.org/'}]}]}
    monkeypatch.setattr(diagnosis.research, 'search', lambda *args: external)
    result = diagnosis.generate('190230', row)
    assert result['external_research'] == external
    assert result['ai'] is None
    assert all(not s['demo'] for s in result['sources'])


def test_ai_failure_keeps_the_evidence(row, monkeypatch):
    monkeypatch.setattr(config, 'DEMO_COMTRADE', False)
    monkeypatch.setattr(config, 'DEMO_TARIFF', False)
    monkeypatch.setattr(diagnosis.research, 'search', lambda *args: {'status': 'unavailable', 'facts': []})
    result = diagnosis.generate('190230', row)
    assert len(result['facts']) == 4
    assert result['ai'] is None


def test_endpoint_requires_matching_analysis_and_keeps_country_scope(client, monkeypatch, row):
    from blueocean.routes import api
    assert client.get('/api/share-diagnosis?hs=bad&iso3=ESP').status_code == 400
    monkeypatch.setattr(api, 'peek', lambda *args: None)
    assert client.get('/api/share-diagnosis?hs=190230&iso3=ESP').status_code == 409
    monkeypatch.setattr(api, 'peek', lambda *args: {'meta': {'base_year': 2024}, 'top20': [copy.deepcopy(row)]})
    assert client.get('/api/share-diagnosis?hs=190230&iso3=USA').status_code == 409
    response = client.get('/api/share-diagnosis?hs=190230&iso3=ESP')
    assert response.status_code == 202
    job = response.get_json()['job_id']
    for _ in range(20):
        response = client.get('/api/jobs/' + job)
        if response.status_code != 202:
            break
        time.sleep(.01)
    assert response.status_code == 200
    assert response.get_json()['iso3'] == 'ESP'
