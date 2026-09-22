"""Central configuration. Reads environment variables (via .env) and exposes
plain module-level constants so the rest of the codebase can do
`from .. import config; config.SOMETHING` without an app-context dependency.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── Flask ──────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
PORT = int(os.getenv("PORT", "5000"))

# ── External API credentials ──────────────────────────────────────────
COMTRADE_API_KEYS = [k.strip() for k in os.getenv("COMTRADE_API_KEYS", "").split(",") if k.strip()]
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
SERPAPI_REQUEST_DELAY_SEC = float(os.getenv("SERPAPI_REQUEST_DELAY_SEC", "0.5").strip() or "0.5")
SERPAPI_MAX_COUNTRIES_PER_RUN = int(os.getenv("SERPAPI_MAX_COUNTRIES_PER_RUN", "10").strip() or "10")
KEXIM_API_KEY = os.getenv("KEXIM_API_KEY", "").strip()

# ── Demo / offline mode ────────────────────────────────────────────────
# "auto"  -> demo mode turns on automatically for any service whose key is
#            missing, so the app runs end-to-end without credentials.
# "1"     -> force demo mode for every service (useful for tests/dev).
# "0"     -> force real network calls even without keys (will raise on use).
_DEMO_RAW = os.getenv("BLUEOCEAN_DEMO_MODE", "auto").strip().lower()


def _demo_for(has_key: bool) -> bool:
    if _DEMO_RAW == "1":
        return True
    if _DEMO_RAW == "0":
        return False
    return not has_key  # "auto"


DEMO_COMTRADE = _demo_for(bool(COMTRADE_API_KEYS))
DEMO_SERPAPI = _demo_for(bool(SERPAPI_KEY))
DEMO_KEXIM = _demo_for(bool(KEXIM_API_KEY))

# ── Data / cache paths ─────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = Path(os.getenv("BLUEOCEAN_CACHE_DIR", str(DATA_DIR / "cache")))
COUNTRY_CODES_CSV = DATA_DIR / "country_codes.csv"
HS_KEYWORD_MAP_CSV = DATA_DIR / "hs_keyword_map.csv"

for _sub in ("comtrade", "trends", "fx", "tariff", "analyze"):
    (CACHE_DIR / _sub).mkdir(parents=True, exist_ok=True)

# 캐시 키에 포함되는 "쿼리 스키마 버전". Comtrade 호출이 실제로 무엇을 요청하는지
# (예: motCode/partner2Code/customsCode 필터) 바꿀 때마다 이 숫자를 올린다. 안 그러면
# 코드는 고쳤는데 예전 쿼리 결과가 TTL(7일) 동안 캐시에서 그대로 재사용되는 사고가 난다
# — 실제로 이 문제 때문에 독일 등 일부 국가의 수입액이 최대 8배로 부풀려진 캐시가
# 남아있었다 (motCode/partner2Code/customsCode를 필터링하지 않아 운송수단×2차 파트너×
# 통관절차 조합별로 쪼개진 행을 전부 합산했었음).
COMTRADE_SCHEMA_VERSION = 3

# 분석에 쓰는 Comtrade 연도 구간. 무료 키는 호출 수가 빠듯한데, reporter="all" 호출은
# 연도 1개당 API 호출 1회씩 소모하므로(comtrade._call_api) 구간을 좁게 고정한다.
# 예전에는 최근 6년 + 국가 상세 그래프는 T-9~T(10년)를 조회해 키가 금방 바닥났다.
#
# 기본값을 2021~2024로 한 근거 (2026-09 화장품 330499 실측, 보고국 수 기준):
#   2021: 80개국 / 2023: 79 / 2024: 77 (러시아·UAE·베트남·에티오피아만 누락, 수입액 3.4%)
#   2025: 64개국 — 중국·대만 등 16개국(2021년 수입액 기준 38.5%)이 아직 미보고라 사용 불가.
# 2018~2021 구간은 기준연도가 코로나 반등기(2021)라 YoY·CAGR이 왜곡되고 5년 묵은 데이터다.
# 최신 연도를 쓰고 싶으면 .env에 COMTRADE_YEAR_FROM/COMTRADE_YEAR_TO만 바꾸면 된다
# (기준연도 T는 이 구간 안에서 커버리지 기준으로 자동 선택되고, 성장률은 T-1·T-3을 쓰므로
# 구간은 최소 4년 권장).
COMTRADE_YEAR_FROM = int(os.getenv("COMTRADE_YEAR_FROM", "2021"))
COMTRADE_YEAR_TO = int(os.getenv("COMTRADE_YEAR_TO", "2024"))
COMTRADE_YEARS = list(range(COMTRADE_YEAR_FROM, COMTRADE_YEAR_TO + 1))

# ── TTLs (seconds) ──────────────────────────────────────────────────────
TTL_COMTRADE = 7 * 24 * 3600
TTL_TRENDS = 7 * 24 * 3600
TTL_FX = 24 * 3600
TTL_TARIFF = 7 * 24 * 3600
TTL_ANALYZE = 24 * 3600

# ── Business rules ───────────────────────────────────────────────────────
HARD_CUT_USD = 10_000_000  # 1,000만 달러 하드컷 (§6.3)
STAGE2_TOP_N = 50
TOP_N_FINAL = 20
GROWTH_FLOOR_PCT = 0.0
GROWTH_CEIL_PCT = 30.0

KOREA_ISO3 = "KOR"
KOREA_COMTRADE_CODE = 410
WORLD_COMTRADE_CODE = 0

# ── KITA TradeNavi (관세율·비관세 장벽) ───────────────────────────────────
# 실측 2차 캡처(2026-09-21, tariffInquiryDetail.do)로 실제 엔드포인트를 확정했다.
#   - 국가코드는 그냥 ISO2였다 (searchNationListOpt=JP, US 등) → country_codes.csv의
#     tradenavi_code(=iso2)를 그대로 쓰면 된다. 별도 크로스워크 불필요.
#   - 요청 바디는 이 엔드포인트에 한해 JSON이 아니라 application/x-www-form-urlencoded다
#     (§5.4.2 최초 가정이 맞았음 — JSON이었던 건 국가 자동완성용 다른 엔드포인트뿐).
#   - `_listSearchParams`는 "뒤로가기 시 이전 목록 상태 복원용" 필드로 보여, 값이 정확히
#     안 맞아도(예: 최초 진입 시나리오) 서버가 무시할 가능성이 높다. 만약 크롤러가
#     계속 ok=False를 반환하면 이 필드부터 의심할 것.
TRADENAVI_URL = os.getenv(
    "TRADENAVI_URL",
    "https://www.kita.net/tradeNavi/tariffInquiry/tariffInquiryDetail.do",
)
TRADENAVI_REFERER = os.getenv(
    "TRADENAVI_REFERER",
    "https://www.kita.net/tradeNavi/tariffInquiry/tariffInquiryDetail.do",
)
TRADENAVI_METHOD = os.getenv("TRADENAVI_METHOD", "POST")
TRADENAVI_PAYLOAD_IS_JSON = False  # 이 엔드포인트는 form 인코딩 (국가검색 API와 다름)
# 비관세장벽은 HS6 그리드가 아니라, 그 그리드에서 찾은 "말단 세번"(예: 330499010)으로
# 이 상세 페이지를 조회해야 나온다 (§5.4.2, 2026-09-21 실측: gridIndex=3).
TRADENAVI_TAX_DETAIL_URL = os.getenv(
    "TRADENAVI_TAX_DETAIL_URL",
    "https://www.kita.net/tradeNavi/tariffInquiry/tariffInquiryTaxDetail.do",
)
TRADENAVI_PAYLOAD_TEMPLATE: dict[str, str] = {
    "tabIndex": "", "hsCondition": "", "ntmNo": "", "rejtNo": "", "dspthNo": "", "reglGrp": "",
    "imRqisitId": "", "nowPageId": "detail", "totalRow": "", "totalColCount": "",
    "pageIndex": "1", "tradeStatus": "", "isLoggedIn": "", "radio01": "export",
    "searchNationListOpt2": "{country}", "searchYear2": "{year}", "searchKeyword2": "{hs}",
    "seq": "", "searchNationListOpt": "{country}", "searchKeyword": "{hs}",
    "searchYear": "{year}", "gridIndex": "2", "screenState": "false",
}
# "관세 조회(pgmId=7657)" 화면에서 나가는 모든 XHR에 공통으로 붙는 고정 헤더.
# base64 값 자체는 페이지 메타데이터(어느 화면인지)일 뿐 세션 토큰이 아니라서 하드코딩해도 된다.
TRADENAVI_EXTRA_HEADERS: dict[str, str] = {
    "ajax": "TRUE",
    "pageauthinfo": "bnVsbA==",
    "pageprograminfo": (
        "eyJwZ21JZCI6Ijc2NTciLCJ1cHBlclBnbUlkIjoiNzY1OCIsInBnbU5hbWUiOiKw/Ly8IMG2yLgiLCJwZ21EdGxOYW1lIjoisKPG7cG2yLgiLCJ1cmwiOiIvdHJhZGVOYXZpL3RhcmlmZklucXVpcnkvdGFyaWZmSW5xdWlyeURldGFpbC5kbyIsIm1lbnVTZXRJZCI6IjI2NDEiLCJtZW51RGVwdGgiOiI0IiwidG9wTWVudUlkIjoiOCIsInRvcE1lbnVOYW1lIjoiv6yxuKGkxeuw6KGksPy8vCIsIm1ickV4dXNZbiI6Ik4iLCJhY2Nlc0F1dGhVc2VZbiI6Ik4iLCJnbnJBY2Nlc1BzYmxZbiI6IlkiLCJtZW51VHlwZUNkIjoiMTAiLCJ0aGVtZSI6IjIiLCJwZ21UaXRsIjoiIiwicGdtRGVzY3IiOiIifQ=="
    ),
}


def tradenavi_configured() -> bool:
    return "<<" not in TRADENAVI_URL and "<<" not in TRADENAVI_REFERER


# 실측값이 채워지기 전까지는 관세 크롤러를 데모(합성 데이터)로 돌려 UI를 바로 확인할 수 있게 한다.
# 실측값을 config.py/.env에 채우는 순간 자동으로 실제 크롤러 경로로 전환된다.
DEMO_TARIFF = _demo_for(tradenavi_configured())

# 캐시 파일은 (함수, 인자)만으로 키를 만들기 때문에, 데모 모드로 만든 결과와 실제 API로
# 받은 결과를 구분하지 못하면 "키를 넣었는데 왜 아직도 더미 데이터냐"는 사고가 난다
# (데모로 개발하다 나중에 키를 넣어도, TTL이 만료되기 전까지 예전 데모 캐시가 그대로
# 응답으로 나가버림). 그래서 각 서비스의 캐시 키에는 이 모드 시그니처를 반드시 포함시켜,
# 모드가 바뀌면 캐시가 자동으로 무효화되고 새로 계산되도록 한다.
#
# COMTRADE_SCHEMA_VERSION도 여기 포함시킨다 — 그래야 comtrade.py의 쿼리 로직을 고쳤을 때
# (예: motCode/partner2Code/customsCode 필터 추가) `/api/analyze`의 최종 캐시된 결과도
# 함께 무효화된다. 이게 없으면 서비스 계층 캐시는 새로 고쳐졌는데 최종 응답만 24시간 동안
# 예전 값(예: 독일 수입액이 8배로 부풀려진 값)을 계속 돌려주는 사고가 난다.
MODE_SIGNATURE = (
    f"comtrade={DEMO_COMTRADE},serpapi={DEMO_SERPAPI},kexim={DEMO_KEXIM},tariff={DEMO_TARIFF},"
    f"schema={COMTRADE_SCHEMA_VERSION},years={COMTRADE_YEAR_FROM}-{COMTRADE_YEAR_TO}"
)
