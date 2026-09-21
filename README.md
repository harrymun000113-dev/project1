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

브라우저에서 `http://localhost:5000` 을 열고 헤더 검색창에 `854140` 같은 HS 코드를 입력하면
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
│                           countries, hs_meta, cache, jobs) — 전부 DataFrame/dict 반환
├─ pipeline/                funnel.py(깔때기), scoring.py(SCORE_SPEC 단일 원천),
│                           respond.py(JSON 직렬화), insight.py(AI Insight stub)
├─ templates/                Jinja2 (base/index + components/*)
└─ static/                   css/app.css, js/(state·popover·globe·charts·ranking_table·main)
data/
├─ country_codes.csv        iso3/iso2/Comtrade 코드/통화/좌표 (80개국)
├─ hs_keyword_map.csv        HS6 -> 검색어·품목 설명
└─ cache/                   Parquet/JSON 파일 캐시 (git에는 포함 안 됨)
tests/                      test_scoring.py, test_funnel.py, test_api.py
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
