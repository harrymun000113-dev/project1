# Blue Ocean Finder

HS 코드 6자리를 입력하면 국가별 수입시장 규모, 성장률, 한국산 점유율, 경쟁국, 관세·환율을 분석하여 유망시장 **최대 20개국**을 보여주는 Flask 웹 앱입니다. 국가를 선택하면 대시보드, AI Insight, 보고서가 같은 국가·품목을 기준으로 갱신됩니다.

이 README는 현재 실행 코드를 기준으로 작성했습니다. 초기 기획 문서와 설명이 다를 경우 현재 구현을 우선 확인하세요.

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 언어 | Python 3.10+, JavaScript (ES6), HTML/CSS |
| 백엔드 | Flask 3 (Blueprint 기반 라우팅, Jinja2 템플릿) |
| 데이터 처리 | pandas, NumPy, PyArrow (Parquet 캐시) |
| 외부 연동 | requests, BeautifulSoup4 (스크래핑), feedparser (RSS), yfinance (환율 보완), python-dotenv (환경설정) |
| 프론트엔드 | Bootstrap 5.3, Tailwind CSS (CDN), Chart.js 4, Globe.gl + Three.js (3D 지구본), Spline (인트로 애니메이션), Pretendard·JetBrains Mono 폰트 |
| AI | OpenAI API — Chat Completions(`gpt-4o-mini`), Responses API `web_search`(`gpt-4.1-mini`) |
| 데이터 소스 | UN Comtrade API (무역 통계), SerpAPI Google Trends (관심도), 한국수출입은행 환율 API, KITA TradeNavi (관세·비관세장벽), Google News RSS (뉴스) |
| 보고서 | python-docx (Word 보고서), 브라우저 인쇄 기반 PDF 저장, Node.js `docx` (보고서 디자인 샘플, `report_redesign/`) |
| 테스트 | pytest (Python), Node.js 기반 JS 단위 테스트 (`tests/*.cjs`) |
| 협업/버전관리 | Git, GitHub |

## 1. 설치 및 실행

Python 3.10 이상을 사용하세요. 일반 앱 실행에는 Node.js가 필요하지 않습니다.

```powershell
# Windows PowerShell · 프로젝트 루트에서 실행
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

macOS/Linux에서는 가상환경 Python 경로를 `.venv/bin/python`으로 바꾸면 됩니다. 이미 환경을 구성했다면 `python app.py`로 실행하세요.

브라우저에서 **http://localhost:5000**에 접속합니다. `app.py`를 브라우저로 직접 여는 방식이 아니라 Flask 서버를 실행하는 방식입니다. 기본 포트는 `5000`이며 `PORT`로 변경할 수 있습니다.

### API 키 없이 기능 확인

```powershell
$env:BLUEOCEAN_DEMO_MODE = "1"
.\.venv\Scripts\python.exe app.py
```

`1`은 무역·트렌드·환율·관세의 합성 데모 데이터를 사용하고 OpenAI 호출을 비활성화합니다. 실제 연동으로 돌아가려면 프로세스를 종료하고 `Remove-Item Env:BLUEOCEAN_DEMO_MODE`로 위 설정을 해제한 뒤 재실행하세요.

데모 수치는 실제 시장의 조사 결과가 아닙니다. 데모 모드에서도 화면의 CDN 라이브러리·폰트·Spline 인트로와 뉴스 조회에는 인터넷 연결이 필요할 수 있습니다. 완전한 오프라인 웹 배포를 의미하지 않습니다.

## 2. 환경 설정과 데이터 연동

프로젝트 루트에 `.env`를 만들고 필요한 항목을 설정합니다. 이미 파일이 있다면 필요한 값만 수정하세요. `.env`는 Git 제외 대상입니다.

```dotenv
BLUEOCEAN_DEMO_MODE=auto
FLASK_DEBUG=0
FLASK_SECRET_KEY=replace-with-your-own-secret
PORT=5000

COMTRADE_API_KEYS=
SERPAPI_KEY=
KEXIM_API_KEY=
OPENAI_API_KEY=

COMTRADE_YEAR_FROM=2021
COMTRADE_YEAR_TO=2024
OPENAI_MODEL=gpt-4o-mini
OPENAI_WEB_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SEC=20
OPENAI_WEB_TIMEOUT_SEC=60
```

위 모델명과 연도는 현재 `config.py`의 기본값입니다. 설정 변경 후 서버를 재시작하세요. OS 환경변수가 이미 설정되어 있으면 `.env`보다 우선할 수 있습니다.

| 설정 / 서비스 | 역할 |
|---|---|
| `COMTRADE_API_KEYS` | UN Comtrade 수입·수출 통계. 여러 키는 쉼표로 구분 |
| `SERPAPI_KEY` | Google Trends 관심도 조회 |
| `KEXIM_API_KEY` | 한국수출입은행 환율. 실패·미고시 통화는 yfinance로 보완 |
| `OPENAI_API_KEY` | AI Insight·Word 보고서 서술, 공식 자료 웹 검색·원문 검증 |
| `OPENAI_MODEL` | Chat Completions 서술 및 원문 검증 모델 |
| `OPENAI_WEB_MODEL` | Responses API의 `web_search` 모델 |
| KITA TradeNavi | 관세율·비관세장벽 조회. 실제 조회 엔드포인트가 설정되어 있음 |
| Google News RSS | 산업·품목·무역 키워드 기반 뉴스 검색. 별도 키 불필요 |
| `BLUEOCEAN_CACHE_DIR` | 캐시 위치. 기본값 `data/cache/` |

`OPEN_API_KEY`도 OpenAI 키의 호환 이름으로 읽지만, 새 설정에는 `OPENAI_API_KEY`를 사용하세요. 둘 다 있으면 정식 이름이 우선합니다. **무역 데이터 API와 OpenAI API는 역할이 다릅니다.** 시장 수치와 점수는 Python에서 계산하고, OpenAI는 서술과 외부 자료 조사에 사용합니다.

### 데모 모드 선택

| 값 | 동작 |
|---|---|
| `auto` (기본값) | 서비스별 키·설정 유무로 실데이터/데모 개별 선택 |
| `1` | 주요 분석 서비스의 데모 모드 강제 |
| `0` | 실제 호출 경로 강제. 자격정보가 없으면 조회에 실패할 수 있음 |

`auto`에서 키가 일부만 있으면 실데이터와 데모 지표가 섞일 수 있습니다. KITA는 키 없이 실제 조회하도록 설정되어 있어, **키가 하나도 없어도 모든 서비스가 자동으로 오프라인 데모가 되는 것은 아닙니다.** 실제 분석에는 응답의 `data_flags`, 출처와 기준연도를 함께 확인하세요.

KITA 설정은 `TRADENAVI_URL`, `TRADENAVI_REFERER`, `TRADENAVI_METHOD`, `TRADENAVI_TAX_DETAIL_URL`로 변경합니다. 현재 관세 조회는 form POST 방식이며 비관세장벽은 세부 세번의 상세 페이지에서도 수집합니다. 사이트 구조 변경·접속 제한으로 조회가 실패할 수 있습니다.

## 3. 화면과 사용 흐름

1. HS 코드 6자리(예: `190230`, `330499`, `854143`)를 입력하고 분석합니다.
2. 첫 조회는 백그라운드 작업으로 실행됩니다. 회전하는 지구본과 분석 상태가 표시되며 완료될 때까지 작업 상태를 조회합니다.
3. 랭킹표 또는 기회 매트릭스에서 국가를 선택합니다.
4. 선택 시장의 수요 잠재력, 한국산 점유율, 경쟁국, 관세·비관세장벽, 추이와 AI Insight를 확인합니다.
5. **보고서 제작**에서 미리보기를 확인하고 PDF로 저장합니다. 별도 메뉴에서 산업 뉴스와 박람회 화면을 볼 수 있습니다.

### 대시보드에 반영된 기능

- **기회 매트릭스:** 한국산 점유율과 수요 잠재력 분포를 표시합니다. 데이터에 맞춰 축 범위를 조정하고 점유율 0% 부근의 버블이 잘리지 않도록 공간을 둡니다.
- **반응형 랭킹표:** 순위, 국가, 점수, 수요 잠재력, 한국산 점유율, 경쟁국 점유율, 전체 시장규모를 표시합니다. 화면 폭에 맞게 열·글자 크기를 조정합니다.
- **한국산 점유율:** 랭킹의 최종 표시 항목은 수입금액이 아닌 **점유율(%)**입니다. 작은 양수가 `0.0%`로 보이지 않도록 소수점 정밀도를 조정합니다. 한국산 수입금액은 보고서 근거와 추이에 별도로 사용합니다.
- **경쟁국 정보:** 국가 수가 아니라 **한국을 제외한 상위 3개 공급국의 합산 점유율(%)**입니다. 공급국 이름과 개별 점유율도 조회합니다.
- **관세·비관세장벽:** 적용 세율 구분, 장벽 목록, 전체 보기, 국가 선택을 제공합니다. 카드 높이와 스크롤 영역을 조정해 항목·버튼의 잘림을 개선했습니다.
- **성장률 카드:** 분석 응답의 YoY·CAGR을 우선 사용합니다. 추이로 보완할 때는 정확히 `T-1`, `T-3`을 비교하며, 자료 부족이나 분모 0으로 계산할 수 없는 값은 만들어 채우지 않습니다.

### AI Insight와 외부 공식 자료

AI Insight는 계산된 지표, OpenAI의 지표 해석, 외부 공식 자료를 결합합니다.

- 숫자와 점수는 모델 응답으로 덮어쓰지 않습니다.
- OpenAI Chat Completions로 요약·선정 이유·해석을 생성합니다. 키가 없거나 호출에 실패하면 규칙 기반 설명으로 대체합니다.
- Market Watch 위험 카드는 수집된 관세·비관세·경쟁·환율 지표를 기준으로 구성합니다.
- 외부 정보는 OpenAI Responses API의 `web_search`로 검색합니다. 허용된 공식 기관 도메인의 인용이 있는 문단을 추리고, 서버에서 원문 HTML을 읽어 다시 검증합니다. 근거 인용문이 실제 원문에 존재하는지도 확인합니다.
- 검증된 자료는 **AI 요약, 원문 근거 문장, 출처 제목·링크, 기관 도메인, 조회일**을 함께 표시합니다. 출처 없는 주장, 추측성 설명, 원문 검증 실패 내용은 표시하지 않습니다.

외부 조사는 OpenAI 사용이 가능하고 무역 데이터가 데모가 아닐 때 실행됩니다. 공식 도메인 목록은 [`research.py`](blueocean/services/research.py)의 `DOMAINS`에서 관리합니다. 현재 HTML 원문만 검증하므로 PDF 자료, 접근 차단 페이지, 허용 목록 밖 출처는 제외될 수 있습니다. 검증 결과가 없으면 외부 자료 영역을 숨기며, 이를 사실이 없다는 결론으로 해석하지 않습니다. 자동 검증은 사람의 검토를 대체하지 않습니다.

## 4. 보고서 미리보기와 저장

보고서는 선택한 국가·HS 코드의 분석 결과를 사용합니다. 요약, 선정 이유, 수입 추이, 리스크·진입장벽, **한국산 점유율 구조·원인 분석**, 액션 체크리스트, 접촉 채널, 종합 결론, 데이터 한계와 산출 근거로 구성됩니다.

### 한국산 점유율 구조·원인 분석

기존 **한국 기업 진출 선례**를 대체한 보고서 4번 항목입니다. 다음 근거를 사용합니다.

- 전체 수입액·한국산 수입액·점유율
- 수집된 상위 공급국 구성과 점유율
- 비교연도 전체 수입 증가와 한국산 수입 증가의 차이
- 조회된 관세·비관세 요건
- 선택 국가·품목에 해당하고 원문 검증을 통과한 외부 공식 자료

통계 비교로 확인되는 구조와 변화만 서술하며, 인지도 부족·유통 독점·물류비 같은 원인을 근거 없이 단정하지 않습니다. 통계 출처에는 조회 조건과 API 조회 링크를 남깁니다. 누락된 한국산 수입 원자료를 원인 분석에서 실제 0으로 간주하지 않으며, 데모 기반의 실제 원인 분석도 표시하지 않습니다.

### PDF 저장

**현재 미리보기 PDF로 저장** 버튼은 브라우저 인쇄 기능을 사용합니다.

- 화면과 인쇄에 동일한 A4 폭·글자·색상·내용 스타일을 적용합니다. 작은 화면에서는 보고서 전체를 축소합니다.
- 저장 시 보고서를 다시 생성하지 않습니다. 진행 중인 점유율 근거 조회를 기다린 후 인쇄 창을 엽니다. 조회 오류가 있으면 다시 조회하도록 안내합니다.
- 저장 설정: **PDF로 저장 / A4 / 배율 100% / 여백 없음 / 머리글·바닥글 끄기**.
- PDF는 브라우저가 페이지를 나눕니다. 용지·배율·여백을 변경하면 미리보기와 배치가 달라질 수 있습니다.

관련 구현은 [`report-output.css`](blueocean/static/css/report-output.css), [`report-output.js`](blueocean/static/js/report-output.js), [`report-share-diagnosis.js`](blueocean/static/js/report-share-diagnosis.js)입니다.

### 다른 내보내기와의 차이

CSV, HTML 스냅샷, Word 다운로드 API도 제공됩니다. **`/api/export.docx`는 `blueocean/reports.py`의 별도 Word 생성기를 사용합니다.** 화면의 최신 점유율 분석·외부 자료·레이아웃을 그대로 저장하는 경로가 아니므로, 현재 미리보기 기준 보고서가 필요하면 PDF 저장을 사용하세요.

`report_redesign/`은 Node.js `docx`로 만든 고정 예시 데이터의 디자인 시안입니다. 앱 실행이나 현재 PDF 저장에 필요한 빌드 단계가 아닙니다.

## 5. 분석 지표와 점수

기준연도 `T`는 설정된 구간에서 선택합니다. 현재 로직은 연도별 수입액 합계가 해당 구간 최대 합계의 80% 이상인 가장 최근 연도를 선택합니다. 최신 달력 연도를 무조건 사용하는 방식이 아닙니다. 기본 구간은 **2021~2024년**이며, 성장률 계산을 위해 최소 4년 구간을 권장합니다.

| 지표 | 계산 기준 |
|---|---|
| 시장규모 | 해당 국가·HS 품목의 기준연도 전체 수입액(USD) |
| 한국산 점유율 | 해당 품목 한국산 수입액 ÷ 전체 수입액 × 100 |
| 전년 대비 성장률 | `(전체 수입액 T / T-1 − 1) × 100` |
| 3년 CAGR | `((전체 수입액 T / T-3)^(1/3) − 1) × 100` |
| 경쟁국 Top3 점유율 | 한국 제외 상위 3개 공급국 수입액 합계 ÷ 해당 국가 전체 수입액 × 100 |
| Export Gap | 한국의 세계 수출 점유율 − 대상국 내 한국산 수입 점유율(%p) |

경쟁국은 국가 코드 파일에 매핑되어 수집된 공급국을 기준으로 합니다. 시장규모는 수입시장 규모이며 현지 생산을 포함한 전체 소비시장 규모와 같지 않습니다.

파이프라인은 **전체 수입규모 1,000만 USD 이상 + Export Gap > 0**인 시장을 추린 뒤 간이 점수 상위 50개국을 정밀 분석하여 최대 20개국을 반환합니다. 조건을 만족하는 국가가 적으면 20개보다 적게 나옵니다.

| 점수 항목 | 배점 |
|---|---:|
| 시장규모 | 15 |
| 3년 성장률 | 15 |
| 1년 성장률 | 10 |
| Google Trends | 5 |
| 3년 환율 변동 | 5 |
| 한국산 점유율 | 25 |
| 경쟁국 Top3 점유율 | 15 |
| 관세율 | 10 |

점수의 기준 구현은 [`scoring.py`](blueocean/pipeline/scoring.py)의 `SCORE_SPEC`입니다. 점수는 정규화된 항목의 **가중합**이며, 전체 항목 계산 시 수요·공급 점수의 산술평균에 해당합니다. 일부 보고서 문구에 남은 기하평균 표현과 구분해야 합니다. 성장률은 0~30%, 관세는 0~25% 고정 범위로 평가하고, 상대평가 항목은 후보군의 P5~P95 범위를 사용합니다. 결측·분산 0인 정규화 값은 중립값 0.5로 처리합니다.

한국산 수입 기록 누락 시 **점수 계산용 입력에서는 0으로 채우는 기존 처리**가 남아 있습니다. 보고서 근거용 원수입액·연도별 기록은 따로 보존하므로, 표시된 점유율 0만으로 실제 한국산 수입이 전혀 없다고 단정하지 마세요.

## 6. 뉴스와 박람회

**산업 뉴스**는 Google News RSS에서 HS Chapter 산업군 + HS6 품목·동의어 + 무역 문맥을 조합해 검색합니다. 결과가 없으면 품목 그룹을 완화한 검색을 한 번 더 시도합니다. 제목·링크·매체·발표일이 있는 기사를 표시합니다.

```text
GET /api/news/hs-code/190230?limit=10&days=30
GET /api/news?hs=190230&limit=10&days=30
```

`product_name`으로 검색어를 보완할 수 있습니다. `limit`은 1~50, `days`는 1~365 범위입니다. 응답에는 `articles`, `count`, 산업군·품목 정보, `query.strategy`가 포함됩니다. 현재 API는 HS 중심 검색이며 화면에서 선택한 국가로 검색이 제한되지는 않습니다. Google News RSS는 정식 개발자 API가 아니므로 장애·형식 변경이 있을 수 있고, 조회 실패 시 `502`를 반환합니다.

검색 매핑은 `data/hs_chapter_industry.csv`와 `data/hs_keyword_map.csv`에서 관리합니다. 미등록 HS6는 Chapter와 코드 표현으로 검색하며 Chapter 77(유보), 98·99(특수 용도)는 별도 구분합니다.

**박람회**는 `/trademap`의 정적 HTML을 iframe으로 표시하고, 선택 HS 코드를 전달해 검색에 반영합니다. 행사 자료는 HTML에 포함된 데이터이므로 실시간 행사 API로 자동 갱신되는 것으로 간주하지 마세요.

## 7. 주요 API

모두 `GET`입니다. 국가 코드는 `ESP`, `DEU` 같은 ISO3를 사용합니다.

| 경로 | 용도 |
|---|---|
| `/api/hs/suggest?q=1902` | 등록된 HS 코드·품목명 검색 |
| `/api/analyze?hs=190230` | 전체 분석. 캐시 적중 시 `200`, 새 작업은 `202 + job_id` |
| `/api/jobs/<job_id>` | 진행 중 `202`, 완료 `200`, 실패 `500`, 없는 작업 `404` |
| `/api/country/ESP/detail?hs=190230` | 국가별 추이·상세·Insight |
| `/api/insight?hs=190230&iso3=ESP` | AI Insight와 외부 공식 자료 |
| `/api/share-diagnosis?hs=190230&iso3=ESP` | 점유율 근거 분석. `202 + job_id`, 해당 분석 캐시가 없으면 `409` |
| `/api/fx/latest` | 최신 USD/KRW 환율·출처·기준일 |
| `/api/score-spec` | 점수 항목·배점·필터 기준 |
| `/api/news/hs-code/<hs_code>` 또는 `/api/news?hs=...` | HS 기반 뉴스 검색 |
| `/api/export.csv?hs=190230` | 랭킹 CSV |
| `/api/export.html?hs=190230` | 별도 HTML 스냅샷 |
| `/api/export.docx?hs=190230&iso3=ESP` | 별도 Word 보고서 |
| `/api/entry-precedents?hs=190230&iso3=ESP` | 기존 진출 기사 검색. 현재 보고서 4번 항목에서는 사용하지 않음 |

HS 코드는 6자리로 입력하세요. 잘못된 입력은 `400`을 반환합니다. 먼저 `/api/analyze` 완료를 확인한 뒤 국가 상세·보고서 근거를 요청하는 순서가 권장됩니다.

## 8. 캐시와 운영 시 참고

| 데이터 | 기본 캐시 유효기간 |
|---|---|
| Comtrade / Trends / 관세 | 7일 |
| 환율 / 분석 결과 / AI Insight 서술 | 24시간 |
| 뉴스 / 외부 공식 자료 조사 | 6시간 |

캐시는 `data/cache/`에 저장하며 Git에 포함하지 않습니다. 분석 캐시 키에는 서비스 모드, 무역 조회 스키마와 연도 구간을 포함합니다. 외부 조사에서 검증 결과가 없는 응답도 캐시될 수 있으므로 모든 클릭이 새로운 외부 조회를 의미하지는 않습니다.

첫 분석과 외부 원문 검증은 API 응답 속도·호출 제한에 따라 오래 걸릴 수 있습니다. 개별 보강 서비스 실패는 가능한 범위에서 결측·중립 점수로 처리하지만, 분석에 필요한 무역 원자료 자체가 없으면 정상 순위를 만들 수 없습니다.

비동기 작업은 현재 **단일 프로세스의 메모리와 스레드**로 관리합니다. 서버 재시작 시 작업 ID가 사라지며, 여러 워커·인스턴스로 배포하려면 작업 상태 저장소와 큐를 별도로 구성해야 합니다. `python app.py`는 로컬 개발 서버 실행 방법입니다.

## 9. 프로젝트 구조

```text
app.py                         Flask 실행 진입점
config.py                      환경변수·연도·데모 모드·캐시·연동 설정
requirements.txt               Python 의존성 (pytest 포함)
blueocean/
  routes/                      화면 및 /api 라우트
  pipeline/
    funnel.py                  국가 필터링·단계별 분석
    scoring.py                 점수 계산의 기준 구현
    respond.py                 응답 직렬화·원수입액·연도별 근거
    insight.py                 AI Insight·지표 기반 위험 카드
    share_diagnosis.py         한국산 점유율 구조·원인 분석
    advice.py                  추천 시장 조합
  services/
    comtrade.py, competitors.py 무역통계·경쟁 공급국
    trends.py, fx.py, tariff.py 트렌드·환율·관세
    openai_client.py            OpenAI Chat Completions 공통 호출
    research.py                공식 자료 검색·인용·원문 검증
    news.py, precedents.py      뉴스 및 기존 진출 기사 검색
    cache.py, jobs.py          파일 캐시·백그라운드 작업
    countries.py, hs_meta.py    국가·HS 메타데이터
  templates/index.html         현재 대시보드·라우팅·보고서 미리보기
  templates/export_snapshot.html 별도 HTML 내보내기
  static/css/                  반응형 랭킹·점유율 근거·보고서 출력 스타일
  static/js/                   공식 자료 표시·보고서 조회·인쇄 등
  static/img/loading-globe.png 분석 로딩 지구본
  static/trademap/index.html   내장 행사 데이터·박람회 화면
  reports.py                   별도 Word 보고서 생성기
data/
  country_codes.csv            분석 대상·공급국 코드 매핑
  hs_keyword_map.csv           HS6 품목명·검색 키워드
  hs_chapter_industry.csv      HS Chapter 산업군·뉴스 검색 키워드
  cache/                      로컬 생성 캐시
tests/                        Python 및 JavaScript 검증
report_redesign/               별도 Word 디자인 시안·예시 데이터
```

현재 메인 화면은 `templates/index.html`입니다. 과거의 `templates/components/`와 일부 정적 JS 파일도 남아 있으므로 UI 수정 시 실제로 로드되는 파일을 먼저 확인하세요.

## 10. 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Python 테스트는 `tests/conftest.py`에서 데모 모드와 임시 캐시를 설정하며, 외부 호출 검증에는 모의 응답을 사용합니다. 실제 API 자격정보나 최신 외부 사이트 가용성을 검사하는 통합 테스트는 아닙니다. Word 다운로드 테스트에는 `requirements.txt`의 `python-docx`가 필요합니다.

프런트엔드의 숫자 표시·경쟁국 표시·성장률 계산 테스트는 Node.js가 있는 환경에서 실행합니다.

```powershell
node tests/test_number_format.cjs
node tests/test_competitor_display.cjs
node tests/test_insight_growth.cjs
```

UI 수정 후에는 브라우저에서도 HS 분석 → 국가 변경 → AI Insight → 보고서 근거 로딩 → PDF 저장을 확인하세요. 창 크기·브라우저 배율을 바꿔 랭킹 열, 비관세 목록, 보고서 미리보기의 잘림 여부를 함께 점검하면 됩니다.
