from __future__ import annotations

import csv
import io
import logging

import pandas as pd
from flask import Blueprint, Response, jsonify, render_template, request, send_file

import config
from ..pipeline import funnel, insight
from ..pipeline.funnel import NoDataError
from ..pipeline.scoring import SCORE_SPEC
from ..services import fx, jobs
from ..services.cache import get_or_compute, peek
from ..services.comtrade import ComtradeError, imports as comtrade_imports
from ..services.countries import load_countries
from ..services.hs_meta import describe_hs6
from ..utils import normalize_hs

log = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")

ANALYZE_CACHE_DIR = config.CACHE_DIR / "analyze"


def _bad_hs():
    return jsonify(error={"code": "BAD_HS", "message": "HS코드를 6자리 숫자로 입력하세요."}), 400


def _empty_result(hs6: str) -> dict:
    from datetime import datetime, timezone, timedelta

    return {
        "meta": {
            "hs6": hs6, "hs_desc": describe_hs6(hs6), "base_year": None,
            "korea_world_share_pct": None, "count": 0,
            "funnel": {"stage1": 0, "stage2": 0, "stage3": 0},
            "stale": False,
            "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        },
        "top20": [],
        "world_market_size_usd": 0,
        "portfolio_advice": {"recommended_iso3": [], "reason": None, "generated_at": None},
        "error": {"code": "NO_DATA", "message": "해당 품목 데이터가 없습니다."},
    }


def _compute_analysis(hs6: str) -> dict:
    try:
        return funnel.run(hs6)
    except NoDataError as e:
        log.info("NO_DATA for hs6=%s: %s", hs6, e)
        return _empty_result(hs6)


def _analyze_cache_key(hs6: str) -> str:
    # config.MODE_SIGNATURE를 넣어, 데모 모드로 만든 이전 결과가 API 키를 넣은 뒤에도
    # (또는 그 반대로) TTL 만료 전까지 그대로 재사용되는 일이 없게 한다.
    return f"analyze:{hs6}:{config.MODE_SIGNATURE}"


def _run_cached(hs6: str) -> dict:
    key = _analyze_cache_key(hs6)
    return get_or_compute(key, lambda: _compute_analysis(hs6), config.TTL_ANALYZE, ANALYZE_CACHE_DIR)


@bp.get("/hs/suggest")
def hs_suggest():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify(items=[])
    try:
        m = pd.read_csv(config.HS_KEYWORD_MAP_CSV, dtype=str)
    except OSError:
        return jsonify(items=[])
    # regex=False: 사용자가 "solar(" 처럼 정규식 메타문자가 섞인 검색어를 입력해도
    # 잘못된 정규식으로 pyarrow/re가 예외를 던지지 않도록 항상 리터럴 문자열로 비교한다.
    mask = (
        m["hs6"].str.startswith(q)
        | m["desc_en"].str.lower().str.contains(q, na=False, regex=False)
        | m["desc_ko"].str.contains(q, na=False, regex=False)
    )
    hits = m[mask].head(10)
    return jsonify(items=[
        {"hs6": r.hs6, "desc_en": r.desc_en, "desc_ko": r.desc_ko} for r in hits.itertuples()
    ])


@bp.get("/analyze")
def analyze():
    hs6, normalized = normalize_hs(request.args.get("hs", ""))
    if not hs6:
        return _bad_hs()

    cached = peek(_analyze_cache_key(hs6), ANALYZE_CACHE_DIR, config.TTL_ANALYZE)
    if cached is not None:
        cached = dict(cached)
        cached["meta"] = {**cached.get("meta", {}), "hs6_normalized": normalized}
        return jsonify(cached)

    job_id = jobs.start(lambda: _run_cached(hs6))
    return jsonify(status="pending", job_id=job_id, hs6=hs6, hs6_normalized=normalized), 202


@bp.get("/jobs/<job_id>")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return jsonify(error={"code": "NOT_FOUND", "message": "작업을 찾을 수 없습니다."}), 404
    if job["status"] == "pending":
        return jsonify(status="pending"), 202
    if job["status"] == "error":
        return jsonify(error={"code": "INTERNAL", "message": "분석 중 오류가 발생했습니다."}), 500
    return jsonify(job["result"])


@bp.get("/country/<iso3>/detail")
def country_detail(iso3: str):
    hs6, _ = normalize_hs(request.args.get("hs", ""))
    if not hs6:
        return _bad_hs()
    iso3 = iso3.upper()
    countries = load_countries()
    if iso3 not in countries.index:
        return jsonify(error={"code": "NOT_FOUND", "message": "알 수 없는 국가 코드입니다."}), 404

    try:
        world_long = comtrade_imports(hs6, reporter="all", partner=config.WORLD_COMTRADE_CODE, years=None)
        T = funnel.pick_base_year(world_long)
        detail = funnel.country_detail(hs6, iso3, T)
    except NoDataError as e:
        return jsonify(error={"code": "NO_DATA", "message": str(e)}), 200
    except ComtradeError as e:
        return jsonify(error={"code": "UPSTREAM_UNAVAILABLE", "message": str(e)}), 502

    detail["insight"] = insight.generate(hs6, _target_row_for_insight(hs6, iso3, countries))
    return jsonify(detail)


def _target_row_for_insight(hs6: str, iso3: str, countries: pd.DataFrame) -> dict:
    """AI Insight가 근거로 쓸 실제 계산값(점수·성장률·관세·경쟁국 등)을 캐시된
    `/api/analyze` 결과에서 찾아 넘긴다. 캐시가 없으면(아직 그 품목을 분석한 적이
    없거나 TTL 만료) 국가명만이라도 채운 최소 정보로 폴백한다 — 이 경우 AI Insight는
    수치 근거 없이 생성되므로 stub에 더 가까운 결과가 나올 수 있다."""
    cached = peek(_analyze_cache_key(hs6), ANALYZE_CACHE_DIR, config.TTL_ANALYZE)
    if cached:
        row = next((r for r in cached.get("top20", []) if r.get("iso3") == iso3), None)
        if row is not None:
            # Insight는 분석 응답의 국가 행과 메타데이터를 함께 사용한다.
            return {
                **row,
                "hs_desc": cached.get("meta", {}).get("hs_desc"),
                "korea_world_share_pct": cached.get("meta", {}).get("korea_world_share_pct"),
                "curr_year": cached.get("meta", {}).get("base_year"),
            }
    return {
        "iso3": iso3,
        "name_ko": countries.loc[iso3, "name_ko"] if iso3 in countries.index else None,
        "name_en": countries.loc[iso3, "name_en"] if iso3 in countries.index else None,
    }


@bp.get("/fx/latest")
def fx_latest():
    try:
        rate, source, as_of = fx.latest_usd_krw()
    except Exception as e:  # 환율 조회는 절대 헤더 토글을 깨뜨리면 안 된다 (§5.3.1)
        log.warning("fx_latest 실패: %s", e)
        rate, source, as_of = None, None, None
    return jsonify(usd_krw=rate, source=source, as_of=as_of)


@bp.get("/export.csv")
def export_csv():
    hs6, _ = normalize_hs(request.args.get("hs", ""))
    if not hs6:
        return _bad_hs()
    data = _run_cached(hs6)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Rank", "ISO2", "Country", "Score", "Growth(YoY %)", "Korea Share(%)",
                      "Top3 Competitor Share(%)", "Market Size(USD)"])
    for row in data.get("top20", []):
        writer.writerow([
            row["rank"], row["iso2"], row["name_en"], row["score"],
            row["growth"]["yoy_pct"], row["korea_share_pct"],
            row["competitors"]["top3_share_pct"], row["market_size_usd"],
        ])
    resp = Response(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=blue_ocean_{hs6}.csv"
    return resp


@bp.get("/export.html")
def export_html():
    hs6, _ = normalize_hs(request.args.get("hs", ""))
    if not hs6:
        return _bad_hs()
    data = _run_cached(hs6)
    html = render_template("export_snapshot.html", data=data)
    resp = Response(html, mimetype="text/html")
    resp.headers["Content-Disposition"] = f"attachment; filename=blue_ocean_{hs6}.html"
    return resp


@bp.get("/export.docx")
def export_docx():
    """선택된 국가 1개에 대한 Word 보고서(`blueocean/reports.py`, v2.6). `/api/analyze`와
    달리 국가 하나를 다루므로 `iso3`가 필수다."""
    hs6, _ = normalize_hs(request.args.get("hs", ""))
    if not hs6:
        return _bad_hs()
    iso3 = (request.args.get("iso3") or "").upper()
    if not iso3:
        return jsonify(error={"code": "BAD_REQUEST", "message": "국가(iso3)를 지정하세요."}), 400

    analyzed = _run_cached(hs6)
    row = next((r for r in analyzed.get("top20", []) if r.get("iso3") == iso3), None)
    if row is None:
        return jsonify(error={"code": "NOT_FOUND", "message": "해당 국가의 분석 결과를 찾을 수 없습니다."}), 404

    from .. import reports

    meta = analyzed.get("meta", {})
    report_data = {
        "country": row.get("name_ko") or row.get("name_en"),
        "blue_ocean_score": row.get("score"),
        "market_opportunity_score": row.get("potential"),
        "penetration_opportunity_score": row.get("supply_score"),
        "growth_1y": row.get("growth", {}).get("yoy_pct"),
        "cagr_3y": row.get("growth", {}).get("cagr3_pct"),
        "korea_market_share": row.get("korea_share_pct"),
        "global_korea_share": meta.get("korea_world_share_pct"),
        "export_gap": row.get("export_gap_pp"),
        "tariff_rate": row.get("barriers", {}).get("tariff_rate_pct"),
        "top3_concentration": row.get("competitors", {}).get("top3_share_pct"),
        "item_name": meta.get("hs_desc") or f"HS {hs6}",
        "hs_code": hs6,
        "project_name": "Blue Ocean Finder",
        "date": (meta.get("generated_at") or "")[:10] or None,
    }

    buf = io.BytesIO()
    try:
        reports.generate_blue_ocean_report(report_data, filename=buf)
    except Exception as e:  # 보고서 생성 실패가 나머지 대시보드를 막으면 안 된다
        log.exception("Word 보고서 생성 실패 (hs=%s, iso3=%s): %s", hs6, iso3, e)
        return jsonify(error={"code": "INTERNAL", "message": "보고서 생성 중 오류가 발생했습니다."}), 500
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name=f"blue_ocean_{hs6}_{iso3}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@bp.get("/score-spec")
def score_spec():
    return jsonify(items=SCORE_SPEC, hard_cut_usd=config.HARD_CUT_USD,
                   growth_floor_pct=config.GROWTH_FLOOR_PCT, growth_ceil_pct=config.GROWTH_CEIL_PCT)
