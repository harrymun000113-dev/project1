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
COMTRADE_SCHEMA_VERSION = 2

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
# 실측 전이므로 "<<" 를 포함한 placeholder로 둔다. tariff.py는 이 값이 채워지지
# 않은 동안 항상 ok=False(중립 점수)를 반환해 파이프라인이 죽지 않게 한다.
TRADENAVI_URL = os.getenv("TRADENAVI_URL", "<<실측: XHR 엔드포인트 URL>>")
TRADENAVI_REFERER = os.getenv("TRADENAVI_REFERER", "<<실측: 해당 조회 화면 URL>>")
TRADENAVI_METHOD = os.getenv("TRADENAVI_METHOD", "POST")
TRADENAVI_PAYLOAD_TEMPLATE: dict[str, str] = {
    "<<실측: HS코드 필드명>>": "{hs}",
    "<<실측: 국가코드 필드명>>": "{country}",
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
    f"schema={COMTRADE_SCHEMA_VERSION}"
)
