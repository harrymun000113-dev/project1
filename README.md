# Blue Ocean Finder

`BLUE_OCEAN_FINDER_SPEC_4.md` 명세를 기반으로 구현한 Flask 앱입니다.
HS 코드 6자리를 입력하면 UN Comtrade·SerpAPI·한국수출입은행/yfinance·KITA 트레이드내비
데이터를 취합해 "시장은 크고 성장 중인데 한국산 침투율은 낮은 나라" Top 20을 100점
만점 점수로 보여줍니다.

## 빠른 시작 (API 키 없이도 바로 실행됩니다)

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://localhost:5000` 을 열고 헤더 검색창에 `854143` 같은 HS 코드를 입력하면
전체 파이프라인(Stage 1~4)이 끝까지 실행됩니다.

### 데모 모드란?

`.env`에 아무 API 키도 넣지 않으면 각 외부 데이터 소스가 **결정론적 합성 데이터**로
자동 대체됩니다(`config.py`의 `DEMO_*` 플래그, `BLUEOCEAN_DEMO_MODE=auto`가 기본값).
같은 HS 코드·국가 조합이면 항상 같은 값이 나오므로, 화면 전체(지구본·버블맵·표·팝오버·
환율 카드 등)를 네트워크 없이 끝까지 눈으로 확인할 수 있습니다.

실제 데이터로 전환하려면 `.env.example`을 `.env`로 복사한 뒤 아래 키를 채우세요.
키가 채워진 소스부터 자동으로 실제 API를 호출합니다(서비스 단위로 개별 전환됨).

| 키 | 채우면 무엇이 바뀌나 |
|---|---|
| `COMTRADE_API_KEYS` | UN Comtrade 실데이터 (시장규모·성장률·한국 점유율·경쟁국) |
| `SERPAPI_KEY` | 구글 트렌드 실데이터 |
| `KEXIM_API_KEY` | 한국수출입은행 환율 실데이터 (미고시 통화는 계속 yfinance로 보조 조회) |
| (없음, `yfinance`) | KEXIM 실패/미고시 통화의 환율 fallback — 키 불필요 |

관세율·비관세 장벽(KITA 트레이드내비)은 XHR 엔드포인트가 아직 실측되지 않아
(§5.4.2) `config.py`의 `TRADENAVI_URL` 등이 `<<실측: ...>>` placeholder로 남아있는
동안은 자동으로 데모 데이터를 반환합니다. 팀이 실제 엔드포인트를 브라우저 개발자도구로
캡처해 `config.py`(또는 `.env`)에 채우면 그 순간부터 실제 크롤러가 동작합니다.

## HS 코드 기반 뉴스 검색

```
GET /api/news/hs-code/{hs_code}?limit=10&days=30&product_name=선택값
```

HS 코드의 (1) Chapter 산업군, (2) HS6 세부 품목명·동의어, (3) 수출입/관세/공급망 같은
무역 문맥 — 세 그룹을 AND로 묶은 검색식으로 Google News RSS를 조회해 관련 기사를
반환합니다. 응답 예:

```json
{
  "hs_code": "850440",
  "chapter": "85",
  "industry": {"ko": "전기기기·전자제품 산업", "en": "Electrical Equipment and Electronics"},
  "product": {"ko": "전력변환장치(어댑터)", "en": "Static Converters (Power Adapters)"},
  "query": {"strategy": "industry_product_trade", "days": 30},
  "count": 2,
  "articles": [
    {"title": "...", "url": "...", "source": "...", "published_at": "...",
     "hs_code": "850440", "chapter": "85", "industry_ko": "...", "industry_en": "...",
     "product_name": "...", "matched_keywords": ["...", "..."]}
  ]
}
```

잘못된 HS 코드는 `400 {"error": {"code": "BAD_HS", ...}}`, Google News RSS 장애는
`502 {"error": {"code": "UPSTREAM_UNAVAILABLE", ...}}`을 반환합니다.

- **API 키 불필요**: Google News RSS(`news.google.com/rss/search`)는 인증 없이 쓰는
  공개 엔드포인트입니다. `.env`에 추가할 값이 없습니다.
- **공식 보장이 없는 엔드포인트입니다.** Google이 제공하는 정식 개발자 API가 아니라서
  URL 형식·응답 구조가 예고 없이 바뀌거나 요청이 막힐 수 있습니다
  (`blueocean/services/news.py` 상단 주석 참고). 장애 시에도 502로만 응답하고 나머지
  대시보드 기능에는 영향을 주지 않습니다.
- 의존성: `feedparser` (RSS 파싱). `pip install -r requirements.txt`에 포함되어 있습니다.
- 결과는 `TTL_NEWS`(6시간) 동안 `data/cache/news/`에 캐시됩니다. 1차 검색식(산업군+품목+
  무역문맥)에 결과가 0건일 때만 품목 그룹을 뺀 완화 검색식으로 한 번 더 시도하며, 응답의
  `query.strategy`로 어느 쪽이 쓰였는지 알 수 있습니다.
- **산업군 매핑 확장 방법**: `data/hs_chapter_industry.csv`에 Chapter(01~99) 한 줄을
  추가/수정하면 됩니다. 컬럼은 `chapter,industry_ko,industry_en,keywords_ko,keywords_en,
  reserved,special`이고 키워드는 `|`로 여러 개를 넣을 수 있습니다(예: `반도체|전자제품`).
  코드 수정 없이 CSV만 고치면 바로 반영됩니다. Chapter 77은 유보 코드(`reserved=1`),
  98·99처럼 국가별 특수 용도 코드는 `special=1`로 표시되어 있어 일반 산업으로
  단정하지 않습니다.
- HS6 세부 품목명·동의어는 기존 `data/hs_keyword_map.csv`를 그대로 재사용합니다(새 데이터
  파일을 만들지 않았습니다). 등록되지 않은 HS6는 Chapter 산업군 + HS 코드 표현만으로
  안전하게 검색을 계속합니다.

## 테스트

```bash
pip install pytest
python -m pytest tests/ -q
```

테스트는 `tests/conftest.py`에서 `BLUEOCEAN_DEMO_MODE=1` + 임시 캐시 디렉터리로
강제 격리되어, 네트워크 없이 항상 동일하게 재현됩니다.

## 구조

```
app.py                     실행 진입점
config.py                  환경변수·경로·TTL·데모모드 스위치
blueocean/
├─ routes/                 pages.py(페이지), api.py(/api/* JSON)
├─ services/                외부 API 클라이언트 (comtrade, trends, fx, tariff, competitors,
│                           countries, hs_meta, cache, jobs, news) — 전부 DataFrame/dict 반환
├─ pipeline/                funnel.py(깔때기), scoring.py(SCORE_SPEC 단일 원천),
│                           respond.py(JSON 직렬화), insight.py(AI Insight stub)
├─ templates/                Jinja2 (base/index + components/*)
└─ static/                   css/app.css, js/(state·popover·globe·charts·ranking_table·main)
data/
├─ country_codes.csv        iso3/iso2/Comtrade 코드/통화/좌표 (80개국)
├─ hs_keyword_map.csv        HS6 -> 검색어·품목 설명
├─ hs_chapter_industry.csv  HS Chapter(01~99) -> 산업군·검색 키워드 (뉴스 검색용)
└─ cache/                   Parquet/JSON 파일 캐시 (git에는 포함 안 됨)
tests/                      test_scoring.py, test_funnel.py, test_api.py, test_news.py
```

## 알아둘 점

- 점수 배점·정규화 로직은 `blueocean/pipeline/scoring.py`의 `SCORE_SPEC` 하나가
  원천입니다. `/api/score-spec`으로 노출되어 프론트 모달(평가기준/수식 명세)이
  같은 값을 렌더링합니다.
- 개별 국가의 외부 API 실패(트렌드·환율·관세)는 그 항목만 중립값(0.5)으로 처리되고
  `data_flags`에 남습니다. 서비스 하나가 통째로 죽어도(네트워크 전면 장애 등) 나머지
  7개 채점 항목과 다른 후보국은 영향받지 않습니다 (`pipeline/funnel.py`의 `_enrich`).
- 첫 조회는 캐시가 없어 수 초~수십 초 걸릴 수 있어 `/api/analyze`가 `202 + job_id`를
  돌려주고, 프론트가 `/api/jobs/<id>`를 폴링합니다.
