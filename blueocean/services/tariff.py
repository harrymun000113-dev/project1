"""KITA 트레이드내비(TradeNavi) — 관세율 · 비관세 장벽 실시간 크롤링 (§5.4).

`config.tradenavi_configured()`가 False인 동안(팀이 실측 XHR 값을 채우기 전)에는
`config.DEMO_TARIFF`가 자동으로 True가 되어 결정론적 합성 데이터를 반환한다 — 그래야
Trade Barriers 카드(§3.5)와 관세율 점수(§4.2 #8)를 처음부터 눈으로 확인할 수 있다.
실측값을 채우고 `BLUEOCEAN_DEMO_MODE`를 auto/0으로 두면 자동으로 실제 크롤러로 전환된다.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

import config
from .cache import disk_json_cache

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

_NTB_POOL = [
    "수입 인증(현지 규격) 요건", "위생·검역(SPS) 서류 요구", "라벨링·현지어 표기 의무",
    "통관 사전신고 절차", "환경 규제(포장재·전자폐기물)", "현지 대리인 지정 의무",
    "쿼터(수량 제한)", "가격 신고 요건",
]


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config.TRADENAVI_REFERER,
        "Origin": "https://www.kita.net",
        **config.TRADENAVI_EXTRA_HEADERS,  # ajax/pageauthinfo/pageprograminfo (§5.4.2 실측)
    })
    try:
        s.get(config.TRADENAVI_REFERER, timeout=10)  # 세션 쿠키 확보 (필요한 경우)
    except requests.RequestException:
        pass
    return s


def _rate_text_to_pct(text: str) -> float | None:
    """'5.8%' -> 5.8, 'Free'/'무세' -> 0.0, 종량세 등 %로 못 바꾸는 표기는 None."""
    text = (text or "").strip()
    if text in ("Free", "무세", "0", "0%"):
        return 0.0
    # 스위스처럼 종량세 단위가 붙은 0 ("0 Fr.")도 실질적으로 무세다.
    if re.match(r"^0+(?:\.0+)?\s*[A-Za-z$€¥.]+$", text):
        return 0.0
    m = re.match(r"^(\d+(?:\.\d+)?)\s*%$", text)
    return float(m.group(1)) if m else None


_PRIORITY_RE = re.compile(r"\((\d+)\s*순위\)")


def _find_tariff_table(soup: BeautifulSoup):
    """"(N순위)" 우선순위 표시가 붙은 세율 그리드(HS 세번 계층 표)를 찾는다.

    이 표는 HS4 -> HS6 -> HS8/10 순으로 계층이 접혀있는 트리 구조라, 각 행 앞쪽의
    HS코드/품목명 칸 개수는 계층 깊이에 따라 달라진다. 뒤쪽 세율 칸의 개수·이름도
    상대국마다 완전히 다르다 (§5.4.2, 2026-09-21 실측) —
      - 일본(RCEP 회원국): 기본세율 / 잠정세율 / WTO세율 / RCEP
      - 미국(양자 FTA국): 기본세율 / KR-US FTA
      - 베트남(RCEP+양자 FTA 둘 다): MFN / AKFTA / VKFTA / RCEP  (기준세율 칼럼명이 "MFN"으로 다름!)
    칼럼 이름을 하드코딩하면 나라마다 깨지므로, 유일하게 공통적인 "(N순위)" 표시
    자체를 앵커로 표를 찾고 우선순위를 읽는다.
    """
    for table in soup.find_all("table"):
        # 국가별로 헤더 행이 <th>가 아니라 <td>로만 렌더링되는 경우도 실측됨(예: 독일/EU) —
        # 그래서 <th>/<td> 둘 다 뒤진다.
        if any(_PRIORITY_RE.search(c.get_text(" ", strip=True)) for c in table.find_all(["th", "td"])):
            return table
    return None


def _extract_rate_columns(header_cells: list[str]) -> tuple[list[str], list[int | None]] | None:
    """헤더에서 첫 "(N순위)" 칼럼부터 끝까지를 "데이터 칼럼 구간"으로 잘라낸다. 없으면 None.

    중국(소비세·증치세), 인도(사회보장세·보상세), 싱가포르(소비세)처럼 세율 칼럼 *뒤에*
    "(N순위)" 표시가 없는 내국세 칼럼이 붙는 나라가 있다 (2026-09-21 실측). 그래서 "뒤쪽
    연속 구간"이 아니라 "첫 순위 칼럼부터 끝까지"를 구간으로 잡고, 칼럼별 우선순위는
    순위 표시가 없는 칼럼(내국세)이면 None으로 둔다 — 이런 칼럼은 관세율로 쓰지 않는다.
    """
    first = next((i for i, h in enumerate(header_cells) if _PRIORITY_RE.search(h)), None)
    if first is None:
        return None
    headers = header_cells[first:]
    priorities = [int(m.group(1)) if (m := _PRIORITY_RE.search(h)) else None for h in headers]
    return headers, priorities


def _parse_rate_table(resp: requests.Response) -> tuple[dict, list[str]]:
    """관세율 그리드 파싱 (§5.4.2, 2026-09-21 실측: tariffInquiryDetail.do?searchKeyword=<HS6>).

    표는 HS코드를 여러 칸(HS4/HS6/HS8·10)으로 쪼개 트리로 보여주고, 실제 세율이 있는
    "말단" 행만 세율 칸에 값이 채워져 있다. 상위 카테고리 행(예: "3304", "--Other")은
    이 칸들이 전부 비어 있어 건너뛴다.

    사이트가 각 세율 칼럼 헤더에 우선순위를 명시해 준다 — "KR-US FTA (1순위)",
    "RCEP (1순위)", "잠정세율 (2순위)", "기본세율/WTO세율/MFN (3순위, 사실상 MFN)" 같은 식.
    칼럼 이름은 상대국마다 다르므로(RCEP 회원국 vs 양자 FTA 체결국 vs 둘 다 없는 나라 vs
    Vietnam처럼 기준세율 칼럼명이 "MFN"인 경우) 이름이 아니라 이 우선순위 숫자로 정렬해,
    값이 있는 것 중 가장 우선순위가 높은 칸을 쓴다.

    반환값의 두 번째 요소는 이 표에서 발견한 "말단 세번"(HS 전체 자리수) 목록이다 —
    비관세장벽은 HS6이 아니라 이 세부 세번으로만 조회가 가능해서(§5.4.2 후속 실측),
    관세율을 구할 때 이미 훑은 표에서 같이 뽑아 재사용한다. HS6 하나에 말단 세번이
    여러 개면(예: 330499010, 330499090) 첫 번째 것을 대표값으로 쓴다.
    """
    soup = BeautifulSoup(resp.text, "html.parser")
    table = _find_tariff_table(soup)
    if table is None:
        # 2022 HS 개정으로 폐지·분할된 코드(예: 854140 -> 854142/854143/854149)는 KITA가 이 문구로
        # 답한다. 이걸 "페이지 구조 변경"으로 뭉뚱그리면 원인을 못 찾는다 (실제로 그랬다).
        if "해당 HS코드가 존재하지 않습니다" in resp.text:
            raise ValueError("KITA에 없는 HS코드입니다 (2022 개정으로 폐지·분할된 코드이거나 이 나라 데이터 없음)")
        raise ValueError("관세율 표를 찾지 못했습니다 (페이지 구조 변경 의심)")

    header_row = table.find("tr")
    if header_row is None:
        raise ValueError("관세율 표에 헤더 행이 없습니다")
    header_cells = [c.get_text(" ", strip=True) for c in header_row.find_all(["th", "td"])]

    rate_cols = _extract_rate_columns(header_cells)
    if rate_cols is None:
        raise ValueError("우선순위(N순위) 표시가 붙은 세율 칼럼을 찾지 못했습니다 (페이지 구조 변경 의심)")
    rate_headers, priorities = rate_cols
    k = len(rate_headers)  # 세율 + 내국세 칼럼을 포함한 데이터 칼럼 구간 길이
    # 우선순위 오름차순(1순위 먼저). 순위 표시 없는 칼럼(내국세)은 관세율 후보에서 제외.
    order = sorted((i for i in range(k) if priorities[i] is not None), key=lambda i: priorities[i])

    tariff_result: dict | None = None
    leaf_codes: list[str] = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) <= k:
            continue
        rate_cells = cells[-k:]
        if not any(rate_cells[i] for i in order):
            continue  # 세율 없는 상위 카테고리 행 (내국세 칸만 차 있는 행 포함)

        hs_parts = cells[:-(k + 1)]  # 세율 칸(k개) + 설명(1개)을 뺀 나머지가 HS코드 조각들
        code = "".join(p for p in hs_parts if p.isdigit())
        if code:
            leaf_codes.append(code)

        if tariff_result is None:
            for i in order:
                pct = _rate_text_to_pct(rate_cells[i])
                if pct is None:
                    continue
                is_mfn = any(x in rate_headers[i] for x in ("기본세율", "WTO세율", "MFN"))
                tariff_result = {"tariff_rate_pct": round(pct, 2), "tariff_type": "MFN" if is_mfn else "FTA"}
                break

    if tariff_result is None:
        # 말단 행은 찾았지만 세율 칸이 전부 %로 환산 안 되는 값(종량세 등)뿐이었던 경우 (§4.2 tariff_non_advalorem)
        raise ValueError("관세율을 %로 환산할 수 있는 행을 찾지 못했습니다 (종량세 등)")
    return tariff_result, leaf_codes


def _parse_ntb(resp: requests.Response) -> list[str]:
    """비관세장벽 목록 파싱 (§5.4.2, 2026-09-21 실측: tariffInquiryTaxDetail.do?searchKeyword=<세부세번>).

    "해외수입요건", "TBT(무역기술장벽)" 등 카테고리별로 <div class="ntb_tit_box"> +
    <ul class="ntb_list"><li>...</li></ul> 가 반복되는 구조. 카테고리 구분 없이 항목
    텍스트만 평평한 리스트로 모은다.
    """
    soup = BeautifulSoup(resp.text, "html.parser")
    container = soup.find("div", class_="ntb_container")
    if container is None:
        return []
    items = []
    for li in container.select("ul.ntb_list li"):
        text = li.get_text(" ", strip=True)
        if text:
            items.append(text)
    return items


def _fetch_ntb_items(hs6: str, country_code: str, leaf_code: str, year: str) -> list[str]:
    """대표 세부세번(leaf_code)으로 tariffInquiryTaxDetail.do를 조회해 비관세장벽만 뽑는다.

    이 호출이 실패해도 관세율은 이미 구했으므로, 예외를 삼키고 빈 목록을 반환한다
    (§3.5 "확인된 비관세 장벽 없음"과 동일하게 표시됨 — 다만 data_flags는 안 남으므로
    관세율 자체가 실패한 경우와는 구분된다).
    """
    payload = {
        "tabIndex": "", "hsCondition": "", "ntmNo": "", "rejtNo": "", "dspthNo": "", "reglGrp": "",
        "imRqisitId": "", "nowPageId": "detail", "totalRow": "", "totalColCount": "", "pageIndex": "1",
        "tradeStatus": "", "isLoggedIn": "", "radio01": "export",
        "searchNationListOpt2": country_code, "searchYear2": year, "searchKeyword2": hs6, "seq": "",
        "searchNationListOpt": country_code, "searchKeyword": leaf_code, "searchYear": year,
        "gridIndex": "3", "screenState": "false",
    }
    try:
        session = _new_session()
        session.headers["Referer"] = (
            f"{config.TRADENAVI_REFERER}?searchNationListOpt={country_code}&searchKeyword={hs6}"
            f"&searchYear={year}&gridIndex=3&screenState=false"
        )
        resp = session.request("POST", config.TRADENAVI_TAX_DETAIL_URL, timeout=10, data=payload)
        if not resp.ok:
            return []
        return _parse_ntb(resp)
    except requests.RequestException as e:
        log.warning("비관세장벽 조회 실패 (hs=%s, country=%s): %s", hs6, country_code, e)
        return []


def _fetch_one_live(hs6: str, country_code: str) -> dict:
    if not config.tradenavi_configured():
        return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}

    # 관세율은 "지금 적용되는" 세율이라 분석 기준연도(T)가 아니라 조회 시점의 연도를 쓴다.
    year = str(pd.Timestamp.now(tz="Asia/Seoul").year)
    payload = {k: v.format(hs=hs6, country=country_code, year=year)
               for k, v in config.TRADENAVI_PAYLOAD_TEMPLATE.items()}
    session = _new_session()
    # searchNationList.do(국가 자동완성)는 JSON 바디였지만, 실제 관세율 상세 엔드포인트
    # (tariffInquiryDetail.do)는 폼(form) 인코딩이다 — 엔드포인트마다 다르므로 플래그로 분기.
    body_kwarg = {"json": payload} if config.TRADENAVI_PAYLOAD_IS_JSON else {"data": payload}

    tariff_result: dict | None = None
    leaf_codes: list[str] = []
    for attempt in range(3):
        time.sleep(random.uniform(0.4, 1.2))
        try:
            resp = session.request(config.TRADENAVI_METHOD, config.TRADENAVI_URL, timeout=10, **body_kwarg)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code in (403, 429):
            time.sleep(2 ** (attempt + 1))
            continue
        if resp.ok:
            try:
                tariff_result, leaf_codes = _parse_rate_table(resp)
                break
            except (KeyError, ValueError) as e:
                log.warning("관세율 파싱 실패 (hs=%s, country=%s): %s", hs6, country_code, e)
                break  # 결측 처리
    if tariff_result is None:
        return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}

    ntb_items = _fetch_ntb_items(hs6, country_code, leaf_codes[0], year) if leaf_codes else []
    return {"ok": True, "fetched_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat(timespec="seconds"),
            **tariff_result, "ntb_items": ntb_items}


def _fetch_one_demo(hs6: str, country_code: str) -> dict:
    seed = int(hashlib.sha1(f"tariff|{hs6}|{country_code}".encode()).hexdigest(), 16) % (2 ** 32)
    rng = np.random.default_rng(seed)
    has_fta = bool(rng.random() < 0.45)
    rate = float(rng.uniform(0.0, 2.0)) if has_fta else float(rng.uniform(0.0, 25.0))
    n_ntb = int(rng.integers(0, 4))
    ntb_items = list(rng.choice(_NTB_POOL, size=n_ntb, replace=False)) if n_ntb else []
    return {
        "ok": True,
        "fetched_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat(timespec="seconds"),
        "tariff_rate_pct": round(rate, 1),
        "tariff_type": "FTA" if has_fta else "MFN",
        "ntb_items": ntb_items,
    }


@disk_json_cache(config.CACHE_DIR / "tariff", config.TTL_TARIFF, cache_if=lambda r: r.get("ok", False))
def _fetch_one_cached(hs6: str, country_code: str, _mode: bool) -> dict:
    # `_mode`(=config.DEMO_TARIFF)는 캐시 키 전용 — 데모/실제 결과가 섞이지 않게 한다.
    if _mode:
        return _fetch_one_demo(hs6, country_code)
    return _fetch_one_live(hs6, country_code)


def _fetch_one(hs6: str, country_code: str) -> dict:
    return _fetch_one_cached(hs6, country_code, config.DEMO_TARIFF)


def fetch_barriers(hs6: str, cand: pd.DataFrame, workers: int = 4) -> pd.DataFrame:
    """후보국(index=iso3, 컬럼 tradenavi_code 필요) 전체의 관세율·비관세장벽 조회."""

    def _safe_fetch(code: str) -> dict:
        try:
            return _fetch_one(hs6, code)
        except Exception as e:  # 크롤러 예외는 이 국가만 결측 처리 (§6.5)
            log.warning("tariff 조회 예외 (country=%s): %s", code, e)
            return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_safe_fetch, cand["tradenavi_code"]))

    return pd.DataFrame({
        "tariff_rate_pct": [r["tariff_rate_pct"] for r in results],
        "tariff_type": [r["tariff_type"] for r in results],
        "ntb_items": [r["ntb_items"] for r in results],
        "ntb_count": [len(r["ntb_items"] or []) for r in results],
        "tariff_ok": [r["ok"] for r in results],
        "tariff_fetched_at": [r["fetched_at"] for r in results],
    }, index=cand.index)
