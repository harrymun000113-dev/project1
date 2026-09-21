import time


def test_index_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Blue Ocean Finder" in resp.data


def test_analyze_rejects_non_numeric_hs(client):
    resp = client.get("/api/analyze?hs=abcd")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_HS"


def _wait_for_analysis(client, hs6, timeout=30):
    resp = client.get(f"/api/analyze?hs={hs6}")
    if resp.status_code == 200:
        return resp.get_json()
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        jresp = client.get(f"/api/jobs/{job_id}")
        if jresp.status_code == 200:
            return jresp.get_json()
        assert jresp.status_code == 202
        time.sleep(0.3)
    raise TimeoutError("analyze job did not finish in time")


def test_analyze_normalizes_hs_code_length(client):
    data = _wait_for_analysis(client, "33072099")  # 8자리 -> 앞 6자리(330720)로 정규화
    assert data["meta"]["hs6"] == "330720"


def test_analyze_returns_top20_schema(client):
    data = _wait_for_analysis(client, "854140")
    assert "top20" in data and "meta" in data
    if data["top20"]:
        row = data["top20"][0]
        for key in ("rank", "iso3", "score", "growth", "competitors", "barriers", "fx", "score_breakdown"):
            assert key in row


def test_score_spec_endpoint_matches_single_source_of_truth(client):
    resp = client.get("/api/score-spec")
    assert resp.status_code == 200
    body = resp.get_json()
    assert sum(item["weight"] for item in body["items"]) == 100


def test_fx_latest_never_errors_even_without_real_credentials(client):
    resp = client.get("/api/fx/latest")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "usd_krw" in body


def test_country_detail_unknown_iso3(client):
    resp = client.get("/api/country/ZZZ/detail?hs=854140")
    assert resp.status_code == 404


def test_hs_suggest_survives_regex_special_characters(client):
    # pandas .str.contains()는 기본값이 regex=True라서, "solar(" 같은 입력이 잘못된
    # 정규식으로 해석되어 500을 던지는 사고가 있었다 (§3.1 자동완성).
    for q in ["solar(", "**", "[abc", "a{2,"]:
        resp = client.get(f"/api/hs/suggest?q={q}")
        assert resp.status_code == 200, f"q={q!r} 에서 500이 발생하면 안 된다"


def test_export_csv_download(client):
    _wait_for_analysis(client, "854140")
    resp = client.get("/api/export.csv?hs=854140")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"Rank" in resp.data
