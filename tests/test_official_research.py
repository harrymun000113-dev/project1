from blueocean.services import research


URL = 'https://www.wto.org/research'


def response(text, url=URL):
    return {'output': [{'type': 'message', 'content': [{'type': 'output_text',
        'text': text + '[source]', 'annotations': [{'type': 'url_citation',
        'start_index': len(text), 'end_index': len(text) + 8, 'url': url, 'title': 'Official source'}]}]}]}


def test_only_cited_official_non_speculative_paragraphs():
    text = '2024년 해당 국가의 품목별 수입액은 원자료에 기록되어 있습니다. '
    assert len(research.extract_facts(response(text))) == 1
    assert research.extract_facts(response(text, 'https://www.wto.org.evil.example/')) == []
    assert research.extract_facts(response('인지도 부족 가능성이 점유율 하락 원인입니다. ')) == []
    assert research.extract_facts({'output': []}) == []


def test_verifier_requires_literal_quote_and_matching_source(monkeypatch):
    quote = 'The reported import value for this product in Spain increased in 2024.'
    monkeypatch.setattr(research, '_page_text', lambda url: quote)
    facts = [{'text': 'candidate', 'sources': [{'url': URL}]}]
    good = {'index': 0, 'url': URL, 'quote': quote, 'text': '2024년 해당 품목 수입액이 증가했습니다.'}
    monkeypatch.setattr(research.openai_client, 'chat_json', lambda *a, **kw: {'facts': [good]})
    assert research.verify_facts(facts, '190230', 'Spain')[0]['quote'] == quote
    for change in [{'quote': 'An invented quotation that does not occur in the source document.'},
                   {'url': 'https://www.wto.org/other'}, {'text': '브랜드 인지도 부족 가능성'}, {'index': 2}]:
        monkeypatch.setattr(research.openai_client, 'chat_json', lambda *a, **kw: {'facts': [dict(good, **change)]})
        assert research.verify_facts(facts, '190230', 'Spain') == []


def test_untrusted_redirect_not_fetched(monkeypatch):
    calls = []
    class Redirect:
        status_code = 302
        headers = {'Location': 'https://untrusted.example/'}
    def get(url, **kwargs):
        calls.append(url)
        return Redirect()
    monkeypatch.setattr(research.requests, 'get', get)
    assert research._page_text(URL) is None
    assert calls == [URL]
