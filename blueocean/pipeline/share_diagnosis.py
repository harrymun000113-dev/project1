"""Evidence-backed explanations; observed patterns are not proven causal effects."""
import math
from urllib.parse import urlencode

import config
from ..services import research


def number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def pct(value):
    if not number(value):
        return "미확인"
    return f"{value:.6g}%"


def money(value):
    return f"${value:,.2f}" if number(value) else "미확인"


def build(hs6, row):
    year, country = row.get("base_year"), row.get("name_ko") or row.get("iso3")
    share = row.get("korea_share_pct")
    demo = config.DEMO_COMTRADE
    sources = []

    def source(sid, title, partner, years=None):
        params = {"period": years or year, "cmdCode": hs6, "flowCode": "M", "reporterCode": row["reporter_code"],
                  "motCode": "0", "partner2Code": "0", "customsCode": "C00"}
        if partner != "all":
            params["partnerCode"] = partner
        sources.append({"id": sid, "title": title, "publisher": "UN Comtrade",
                        "url": "https://comtradeplus.un.org/", "query_url": "https://comtradeapi.un.org/data/v1/get/C/A/HS?" + urlencode(params),
                        "scope": f"보고국 {country} ({row['reporter_code']}) · HS {hs6} · {params['period']}년 · 수입 · 상대국 {partner}",
                        "date": row.get("generated_at"), "date_label": "분석 생성일",
                        "demo": demo})

    source("S1", "해당 품목 전체 수입 및 한국산 수입", 0)
    source("S2", "한국산 수입 원자료", 410)
    source("S3", "공급국별 수입 내역", "all")
    facts = []

    def add(fid, title, observation, interpretation, limits, refs):
        if '미확인' in observation:
            return
        facts.append({"id": fid, "title": title, "observation": observation,
                      "interpretation": interpretation, "limitation": limits, "source_ids": refs})

    add("F1", "한국산의 실제 공급 규모", f"{year}년 전체 수입 {money(row.get('market_size_usd'))}, 한국산 수입 {money(row.get('korea_import_usd'))}, 한국산 점유율 {pct(share)}.",
        "이 비율은 해당 HS 품목 수입에서 한국 원산지 상품이 차지하는 비중입니다. 낮은 점유율은 분석할 현상이지 그 자체가 원인은 아닙니다.",
        "기업 국적별 판매 점유율이나 현지 생산·매출은 이 통계로 확인할 수 없습니다.", ["S1", "S2"])
    competitors = row.get("competitors") or {}
    concentration = competitors.get("top3_share_pct")
    top = competitors.get("top3") or []
    if number(concentration) and top:
        names = ", ".join(f"{p.get('name_ko') or p.get('iso3')} {pct(p.get('share_pct'))}" for p in top)
        leader = max(top, key=lambda p: p.get("share_pct") if number(p.get("share_pct")) else -1)
        comparison = ""
        if number(share) and share > 0 and number(leader.get("share_pct")):
            comparison = f" 최대 공급국 {leader.get('name_ko') or leader.get('iso3')}의 비중은 한국산의 약 {leader['share_pct'] / share:.1f}배입니다."
        if concentration >= 50:
            interpretation = f"수집된 경쟁 공급국 중 상위 3개국의 비중이 절반 이상입니다. 나머지 공급국과 한국산의 합산 비중은 {pct(100-concentration)}입니다."
        else:
            interpretation = f"수집된 상위 3개 공급국의 비중은 절반 미만이며, 나머지 공급국과 한국산의 합산 비중은 {pct(100-concentration)}입니다."
        add("F2", "어느 공급국이 시장을 차지하는가", f"한국 제외 상위 공급국: {names}. 합산 {pct(concentration)}." + comparison,
            interpretation, "국가 목록에 매핑되어 수집된 공급국 기준입니다. 수입 점유율은 유통 지배력·브랜드 선호의 직접 증거가 아닙니다.", ["S3"])

    history = sorted([p for p in row.get("korea_import_history", []) if number(p.get("year")) and
                      number(p.get("total_import_usd")) and p["total_import_usd"] > 0 and number(p.get("korea_import_usd"))], key=lambda p: p["year"])
    if len(history) >= 2:
        first, last = history[0], history[-1]
        market_growth = (last["total_import_usd"] / first["total_import_usd"] - 1) * 100
        korea_growth = (last["korea_import_usd"] / first["korea_import_usd"] - 1) * 100 if first["korea_import_usd"] > 0 else None
        old_share = first["korea_import_usd"] / first["total_import_usd"] * 100
        new_share = last["korea_import_usd"] / last["total_import_usd"] * 100
        korea_change = f" ({pct(korea_growth)})" if korea_growth is not None else ""
        observation = (f"{first['year']}→{last['year']}년 전체 수입 {money(first['total_import_usd'])}→{money(last['total_import_usd'])} ({pct(market_growth)}), "
                       f"한국산 {money(first['korea_import_usd'])}→{money(last['korea_import_usd'])}{korea_change}. 한국산 비중 {pct(old_share)}→{pct(new_share)}.")
        if new_share < old_share:
            interpretation = "한국산 수입 증가가 전체 수입 증가를 따라가지 못해 점유율이 낮아졌습니다." if market_growth > 0 else "시장 축소 과정에서 한국산 수입이 전체 수입보다 더 크게 줄어 점유율이 낮아졌습니다."
        elif new_share > old_share:
            interpretation = "한국산 비중은 비교기간 동안 상승했습니다. 한국산 수입액이 전체 수입액보다 높은 증가율을 기록했습니다." if first['korea_import_usd'] > 0 else "시작연도 한국산 수입액은 0이었고 비교연도에 한국산 수입이 기록되었습니다."
        else:
            interpretation = "비교기간의 한국산 비중이 유지됐습니다. 최근 하락보다는 기존의 작은 공급 규모가 지속되는 양상입니다."
        period = f"{first['year']},{last['year']}"
        source("S4", "비교연도 전체 수입", 0, period)
        source("S5", "비교연도 한국산 수입", 410, period)
        add("F3", "수요 증가를 한국산 공급이 따라갔는가", observation, interpretation,
            "이는 금액 기준 증감 분해입니다. 가격·환율·수량 변화 및 바이어 선택의 원인을 분리하지 못합니다. 시작연도 한국산 수입이 0이면 증가율은 정의하지 않습니다.", ["S4", "S5"])

    barriers = row.get("barriers") or {}
    rate, items = barriers.get("tariff_rate_pct"), barriers.get("ntb_items") or []
    if number(rate) or items:
        sources.append({"id": "S6", "title": "관세·비관세장벽 조회", "publisher": "KITA TradeNavi",
                        "url": config.TRADENAVI_REFERER, "scope": f"{country} ({row.get('iso2')}) · HS {hs6} · {barriers.get('tariff_type') or '세율 구분 미확인'}",
                        "date": barriers.get("fetched_at"), "date_label": "수집일", "demo": config.DEMO_TARIFF})
        interpretation = "조회 조건에서 관세율은 0%입니다. 아래 비관세 요건은 관세율과 별도로 수집된 항목입니다." if rate == 0 else f"조회 조건의 관세율은 {pct(rate)}이며, 아래 항목은 해당 품목에 등록된 비관세 요건입니다."
        if items:
            interpretation += " 규정 적용 범위는 품목의 세부 사양·용도에 따라 구분됩니다."
        add("F4", "관세·규제가 설명하는 범위", f"관세 {pct(rate)}, 비관세장벽 {len(items)}건. " + " / ".join(str(i) for i in items[:3]),
            interpretation, "조회 시점과 무역 기준연도가 다를 수 있습니다. HS6보다 세분된 세번·용도·원산지 조건과 규정 원문을 확인해야 합니다.", ["S6"])

    sources.append({"id": "S7", "title": "무역통계의 상대국·원산지 정의", "publisher": "UN Comtrade",
                    "url": "https://comtrade.un.org/data/MethodologyGuideforComtradePlus.pdf",
                    "scope": "수입 상대국: 원산지 및 적출국 구분", "date": None, "demo": False})
    return {"hs_code": hs6, "iso3": row["iso3"], "country": country, "year": year, "facts": facts, "sources": sources,
            "summary": "확인된 공급국 구성·수입 증감·진입요건과 공식 원문에 출처가 있는 사실만 표시합니다.",
            "mode": "demo" if demo else "observed", "ai": None,
            "limitations": ["수입 통계만으로 소비자 취향·브랜드 인지도·물류비·독점 유통계약을 원인으로 확정할 수 없습니다.",
                            "HS6에는 여러 제품·가격대가 포함될 수 있습니다. 한국산 원산지 점유율과 한국 기업의 세계 생산품 판매 점유율은 다릅니다. [S7]",
                            "공식 조회 링크는 재검증 경로입니다. API 원자료 링크는 UN Comtrade 접근 권한이 필요할 수 있으며, 집계는 이후 개정될 수 있습니다."]}


def generate(hs6, row):
    result = build(hs6, row)
    if result["mode"] == "demo":
        result["facts"] = []
        result["external_research"] = {"status": "disabled", "facts": []}
        return result
    result["external_research"] = research.search(hs6, row["iso3"], result["country"])
    used = {sid for fact in result["facts"] for sid in fact["source_ids"]}
    result["sources"] = [s for s in result["sources"] if s["id"] in used and not s.get("demo")]
    result["facts"] = [f for f in result["facts"] if all(s in {v["id"] for v in result["sources"]} for s in f["source_ids"])]
    return result
