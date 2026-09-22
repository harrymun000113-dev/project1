# Blue Ocean Finder

## GitHub로 Comtrade 캐시 공유

처리 순서: **HS 코드 검색 → Comtrade API 응답 원본 JSON 저장 → 전처리 → SCORE 계산**. 같은 요청의 원본 JSON이 있으면 API를 다시 호출하지 않고 전처리부터 실행합니다. 원본은 `data/comtrade_raw/`에 저장되며, API 키는 파일에 포함되지 않습니다. 원본 JSON은 Git에 추가해 공유할 수 있습니다.

기존 `data/comtrade_shared/`의 Parquet은 전처리된 수출입 데이터입니다. 이미 Parquet에만 저장된 과거 조회의 원본 JSON은 복원할 수 없습니다. 다만 해당 Parquet이 유효하면 원본 JSON이 없어도 API를 다시 호출하지 않습니다.

실제 Comtrade 조회 결과는 `data/comtrade_shared/`에도 Parquet으로 저장됩니다. 이 폴더를 Git에 커밋하면 다른 사람이 저장소를 받은 뒤 동일한 HS 코드·수출입 구분·국가·연도 조회에 재사용할 수 있습니다. `data/cache/`는 실행 중 사용하는 임시 캐시이므로 계속 Git에서 제외합니다.

공유 파일은 현재 Comtrade 조회 스키마와 실제 데이터 모드에서만 사용합니다. 과거 스키마로 받은 파일은 집계 방식이 달라 현재 결과에 섞이지 않습니다. 공유 파일은 자동 만료되지 않으므로 데이터를 새로 받아야 할 때는 해당 공유 파일과 로컬 캐시를 삭제한 뒤 다시 조회하세요. 새로 생성된 공유 파일은 Git에 추가하고 커밋해야 다른 사람에게 전달됩니다. API 인증 키가 들어 있는 `.env`는 공유하지 마세요.

현재 저장된 실데이터 캐시는 HS `190230`, `220299`의 조회 결과입니다. Comtrade 키 없이 실행하면 데모 모드가 켜지므로 이 실데이터 캐시를 사용하려면 수신자도 실데이터 모드로 실행해야 합니다.

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
