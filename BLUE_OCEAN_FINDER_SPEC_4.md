# Blue Ocean Finder — UI · 컴포넌트 · 데이터 연동 명세서

> 문서 버전: v2.4 (환율 yfinance Fallback 반영) · 작성일: 2026-09-20
> 대상 독자: Flask / Python / Pandas로 구현을 시작하는 개발자
> 근거 자료: 대시보드 UI 초안 이미지 2장(Hero 화면, Dashboard 화면), 점수 배분표 이미지 1장

---

## 0. 문서 개요

### 0.1 서비스 한 줄 요약

사용자가 **HS Code(6자리)** 를 입력하면, 전 세계 수입국을 분석해 **"시장은 크고 성장 중인데 한국산 침투율은 낮은 나라"** 상위 20개를 100점 만점 점수로 보여주는 수출 타깃국 분석 서비스.

### 0.2 이 문서에서 쓰는 용어

| 용어 | 정의 |
|---|---|
| 타깃국 | 분석 대상 수입국. 한국(KOR)은 항상 제외 |
| 시장 규모 | 해당 국가의 해당 HS 품목 총수입액(USD), 최신 연도 기준 |
| 한국 점유율 | 타깃국의 해당 품목 총수입액 중 한국산 비중(%) |
| 한국 세계 점유율 | 세계 전체 수출액 중 한국 수출액 비중(%) |
| Export Gap(침투 타깃 Gap) | `한국 세계 점유율 − 한국 점유율` (단위 %p). 양수면 "한국이 그 나라에서 세계 평균보다 못 팔고 있음" |
| 수요 잠재력(Potential) | 8개 점수 항목 중 **수요 측 5개 항목**(시장 규모·3년·1년 성장률·구글 트렌드·환율)의 획득점을 100점으로 환산한 값. Hero의 HUD와 버블맵 Y축에 사용 |
| T | 분석 기준 연도. Comtrade에서 데이터가 충분히 확보된 가장 최근 연도 (§6.2 참고) |

### 0.3 기술 스택 전제

- 백엔드: **Python 3.11+, Flask, Pandas, NumPy, requests, yfinance(환율 보조)**
- 프론트: Jinja2 템플릿 + Bootstrap 5(또는 동급 CSS) + Chart.js(차트) + Three.js/globe.gl(3D 지구본)
- 저장: 파일 캐시(Parquet/JSON) 또는 SQLite. 별도 DB 서버는 v1에서 불필요

---

## 1. 이번 개정에서 바뀐 것 (초안 → v2.0)

| # | 구분 | 대상 | 변경 내용 |
|---|---|---|---|
| 1 | **삭제** | 좌측 5개 아이콘 사이드바 | 우측 상단 헤더 서브메뉴와 기능이 중복되므로 완전 삭제. 레이아웃은 사이드바 폭만큼 좌측 여백 제거 후 전체 폭 사용 |
| 2 | **삭제** | 하단 `Utility / Item Analysis` 바 | 품목·시장 드롭다운, Target Score 배지, `1차 사냥 필터` 체크박스 전부 삭제 (대체 방법은 §1.1) |
| 3 | **이동·조정** | `AI Insight` | 좌측 하단 → Hero(지구본 + 락온 HUD) **바로 아래 중앙**으로 이동. 가로·세로 크기를 지구본 박스와 유사하게 맞춤 |
| 4 | **수정** | Top 20 표 `Penetration` | 컬럼명 → **`한국 점유율`** |
| 5 | **수정** | Top 20 표 `Potential` | 컬럼명 → **`Growth 추세`**. 수치 대신 ⬆️/⬇️ 표시, 클릭 시 전년대비 수입성장률 수치 노출 |
| 6 | **수정** | Top 20 표 `경쟁국(Top3)` | 컬럼명 → **`경쟁국`**. 기본값은 Top 3 경쟁국 점유율 수치, 클릭 시 국가 이름 노출 |
| 7 | **추가** | 데이터 연동 | UN Comtrade / SerpAPI / **한국수출입은행(환율, 주) + yfinance(환율, 보조)** + Pandas 파이프라인 |
| 8 | **추가** | 점수식 | 100점 만점 8개 항목 산정 공식 (§4) |
| 9 | **변경(v2.1)** | 시장규모 하드컷 | 500만 → **1,000만 달러** 미만 국가 제외 |
| 10 | **변경(v2.1)** | 성장률 점수 | 역성장 0점, +30% 이상 만점, 0~30% 선형 (§4.2) |
| 11 | **변경(v2.3)** | 환율 소스 | Exchange Rate API → **한국수출입은행 오픈 API(주)** — 3년치 시계열 없이 **오늘 vs 3년 전 두 시점만** 비교 (§5.3) |
| 12 | **추가(v2.1)** | C-5 환율 카드 | 국가 클릭 시 해당국 통화 ↔ KRW **3년 전 vs 현재** 비교 그래프 (§3.6) |
| 13 | **추가(v2.2)** | 관세율·비관세 장벽 | KITA 트레이드내비 XHR 엔드포인트를 `requests`로 실시간 크롤링 (헤더 위장 + TTL 캐시) (§5.4) |
| 14 | **삭제(v2.3)** | Trade Show Schedule | 컴포넌트 삭제 (KOTRA 박람회 연동 제거) |
| 15 | **추가(v2.3)** | C-1 Trade Barriers | 삭제한 자리(AI Insight 아래·좌측·환율 카드 위)에 관세율·비관세 장벽 카드 (§3.5) |
| 16 | **변경(v2.3)** | 성장률 점수 | 임계값 조정 없이 **절대평가**로 확정 (§4.2) |
| 17 | **추가(v2.4)** | 환율 Fallback | 수출입은행 미고시 통화(MXN·VND·PLN 등)는 `try / except`로 에러 없이 **yfinance 보조 조회** (§5.3) |

### 1.1 Utility 바 삭제에 따른 기능 이관

Utility 바가 하던 일은 아래와 같이 다른 곳으로 옮긴다. **이관 대상이 없으면 기능이 사라지므로 반드시 확인.**

| 기존 Utility 기능 | v2.0에서의 대체 |
|---|---|
| Item Analysis (품목 선택) | 헤더의 **HS Code 검색창** 단일 진입점 |
| Base Market / Select Market (시장 선택) | ① 지구본의 타깃 점·하단 타깃 칩 클릭 ② Top 20 표의 행 클릭 ③ HUD의 `다음 타깃` 버튼 — 모두 동일한 전역 상태 `selectedIso3`를 바꿈 (§3.10) |
| Target Score 배지 (87/100) | 락온 HUD의 Blue Ocean Score로 통합 (이미 존재) |
| `1차 사냥 필터 (Export Gap > 0)` 체크박스 | **UI에서 제거하고 백엔드 고정 규칙으로 승격.** 깔때기 1단계에서 항상 적용 (§6.3). 사용자가 끌 수 없음 |

---

## 2. 화면 구조 (Layout)

### 2.1 전체 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER   Logo | HUNT MODE | [HS code search] | nav... | CSV | HTML | USD/KRW │
├──────────────────────────────────────────────────────────────────────────────┤
│ SECTION A - HERO  (2 columns, 5 : 7)                                         │
│ ┌────────────────────────────┐ ┌───────────────────────────────────────────┐ │
│ │ A-1  Headline              │ │ A-2  3D Hunting Globe   == GLOBE BOX ==   │ │
│ │      Locked Target HUD     │ │      (arcs Seoul -> targets, target chips)│ │
│ └────────────────────────────┘ └───────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ SECTION B - AI INSIGHT  (centered, width x height ~= GLOBE BOX)              │
│                  ┌────────────────────────────────────┐                      │
│                  │ B-1  AI Insight                    │                      │
│                  └────────────────────────────────────┘                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ SECTION C - DASHBOARD GRID  (3 columns, 3 : 5 : 4)                           │
│ ┌────────────┐ ┌────────────────────────────┐ ┌────────────────────────────┐ │
│ │ C-1 Tariff │ │ C-2 Global Blue Ocean Map  │ │ C-3 Top 20 Blue Ocean      │ │
│ │ & NTB      │ │     (bubble chart)         │ │     Market Rankings        │ │
│ │ Card       │ ├────────────────────────────┤ │     (data table)           │ │
│ ├────────────┤ │ C-4 Export Gap Trend       │ │                            │ │
│ │ C-5 FX     │ │     (bar + line chart)     │ │                            │ │
│ │ Rate       │ │                            │ │                            │ │
│ └────────────┘ └────────────────────────────┘ └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Flask 템플릿 / 컨테이너 매핑

| 영역 | Jinja partial | 컨테이너(권장 클래스) | 그리드 |
|---|---|---|---|
| Header | `components/_header.html` | `<header class="app-header sticky-top">` | flex, space-between |
| A-1 / A-2 | `components/_hero.html` | `<section id="hero" class="row g-4">` | `col-lg-5` / `col-lg-7` |
| B | `components/_ai_insight.html` | `<section id="ai-insight" class="ai-insight-wrap">` | 중앙 정렬 단일 컬럼 (§3.4) |
| C 전체 | `components/_dashboard.html` | `<section id="dashboard" class="row g-4 align-items-stretch">` | `col-lg-3` / `col-lg-5` / `col-lg-4` |
| C-1, C-5 | `_trade_barriers.html`, `_fx_rate.html` | 왼쪽 컬럼 내부 세로 스택 (`d-flex flex-column gap-4`) | 카드 2개가 컬럼 높이를 나눠 채움 |
| C-2, C-4 | `_blue_ocean_map.html`, `_export_gap_trend.html` | 가운데 컬럼 세로 스택 | 카드 2개 |
| C-3 | `_ranking_table.html` | 오른쪽 컬럼, 카드 1개 | 카드 높이 = 가운데 컬럼 합계 높이 |

### 2.3 레이아웃 규칙

1. 사이드바가 없으므로 컨테이너는 `max-width: 1600px; margin: 0 auto; padding: 0 24px`.
2. Section C의 세 컬럼은 **높이를 동일하게 stretch**. AI Insight가 좌측 컬럼에서 빠져 좌측이 짧아지므로, C-1·C-5 카드에 `flex: 1`을 주어 남는 높이를 채운다.
3. Top 20 표는 카드 높이가 고정이므로 **표 본문만 내부 스크롤**(`overflow-y: auto`), 헤더 행은 `position: sticky; top: 0`.
4. 반응형: `< 992px`에서는 A → B → C-3 → C-2 → C-4 → C-1 → C-5 순서로 1열 스택.

---

## 3. 컴포넌트 명세

### 3.1 Header (`_header.html`)

| 요소 | 동작 |
|---|---|
| 로고 `Blue Ocean Finder` + `HUNT MODE` 배지 | 클릭 시 `/` 이동 |
| HS Code 검색창 | placeholder `HS코드 입력 후 Enter (예: 330720)`. 숫자만 허용, **6자리로 정규화** (4·8·10자리 입력 시 앞 6자리 사용 + "6자리로 분석합니다" 토스트). 제출 시 `GET /api/analyze?hs=`. 입력 중 `GET /api/hs/suggest?q=` 자동완성(선택) |
| 서브메뉴 `3D 헌팅 지구본` | `#hero`로 스크롤 |
| 서브메뉴 `분석 대시보드` | `#dashboard`로 스크롤 |
| 서브메뉴 `평가기준(100점)` | 모달. §4.1 배점표를 `SCORE_SPEC`에서 렌더링 |
| 서브메뉴 `수식 명세` | 모달. §4.2 계산식을 `SCORE_SPEC`에서 렌더링 |
| `Export (CSV)` | `GET /api/export.csv?hs=` — 현재 Top 20 다운로드 |
| `HTML 코드 다운로드` | 현재 분석 결과를 정적 HTML 1파일로 저장 (`GET /api/export.html?hs=`) |
| `USD ($) / KRW (₩)` 토글 | 모든 금액 표기(시장규모, 차트 축, 툴팁)를 클라이언트에서 환산. 환율은 `/api/fx/latest`(한국수출입은행 USD 고시환율, 실패 시 yfinance)의 USD→KRW 사용. 기본값 USD |

> 사이드바 삭제로 **내비게이션은 헤더 하나로 통일**된다. 모바일에서는 서브메뉴를 햄버거로 접는다.

### 3.2 A-1 · 헤드라인 + Locked Target HUD

**헤드라인**: `한국에서 전 세계로 발사되는 / 미개척 블루오션 정밀 타깃 락온` + 설명문 (정적 텍스트).

**Locked Target HUD** — 현재 선택된 타깃국(`selectedIso3`)의 요약 카드.

| 필드 | 표기 예 | 데이터 필드 |
|---|---|---|
| 상태 점 + `LOCKED TARGET HUD` | 초록 점 | 정적 |
| 랭크 배지 | `TARGET #1 (최우선)` | `rank` (1위만 "(최우선)" 붙임) |
| 국가 약어 원형 아이콘 | `ME` | `iso2` |
| 국가명 | `Mexico (멕시코)` | `name_en`, `name_ko` |
| 품목 라인 | `HS 854140 Solar Cells & Modules` | `hs6`, `hs_desc` (Comtrade 품목명) |
| Blue Ocean Score | `87/100` | `score` |
| 수요 잠재력 | `88.5` | `potential` |
| 한국 점유율 | `1.2%` | `korea_share_pct` |
| 침투 타깃(Gap) | `+15.4%p` (빨강) | `export_gap_pp` |
| CTA `이 먹잇감 상세 분석 락온 ↓` | 클릭 시 `#dashboard`로 스크롤 + C-3에서 해당 행 하이라이트 | — |
| `다음 타깃 ↻` | `selectedIso3`를 Top 20 순서상 다음 국가로 이동(마지막 → 1위 순환) | — |

### 3.3 A-2 · 3D 헌팅 지구본 (= "GLOBE BOX")

- 상단 라벨: `ORIGIN: SEOUL, KOREA (37.5°N, 127.0°E) → HUNTING {n} GLOBAL TARGETS` (n = 표시 중인 타깃 수, 기본 6)
- 렌더링: Three.js 또는 globe.gl. 서울에서 각 타깃국 수도(또는 중심 좌표)로 **호(arc)** 를 그린다. 선택된 타깃은 **빨강 호 + 빨강 점**, 나머지는 파랑.
- 조작: 드래그 회전, 우측 상단 `+ / − / 리셋` 버튼. 타깃 점 클릭 = 타깃 선택.
- 하단 **타깃 칩 바**: Top 20 중 상위 6개를 `[ISO2] 국가명 +{export_gap_pp}%p` 형태로 표시. 선택된 칩은 빨강 테두리.
- 안내문: `마우스로 3D 지구를 드래그하여 회전할 수 있으며, 붉은 타깃 점을 클릭하면 즉시 락온됩니다.`
- 크기 기준: 이 박스의 **너비/높이가 Section B(AI Insight)의 기준값**이다. CSS 변수로 공유한다 (§3.4).

### 3.4 B · AI Insight (위치·크기 변경)

**위치**: Hero 섹션 바로 아래, 페이지 **가로 중앙 고정**.

**크기 규칙**: 지구본 박스와 시각적으로 같은 크기.

```css
:root {
  --hero-box-h: 420px;          /* 지구본 박스 높이 (초안 기준 약 420px) */
  --hero-box-w-ratio: 7 / 12;   /* 지구본 박스 폭 = Hero 컨테이너의 7/12 (초안 기준 약 57%) */
}
.globe-box   { height: var(--hero-box-h); }
.ai-insight  {
  width: calc(100% * var(--hero-box-w-ratio));
  min-height: var(--hero-box-h);
  margin-inline: auto;          /* 중앙 고정 */
}
@media (max-width: 991px) { .ai-insight { width: 100%; min-height: auto; } }
```

- 두 박스가 같은 CSS 변수를 쓰므로, 지구본 크기를 바꾸면 AI Insight도 함께 따라간다. 수 px 차이는 허용.
- **내부 구성 (보류)**: 콘텐츠·고정 프롬프트는 **데이터 처리·가공 파이프라인 완성 이후에 확정**한다. 그때까지는 위치·크기(레이아웃)만 먼저 구현하고, 내부는 아래 4블록을 **임시(placeholder) 구성**으로 둔다:

| 블록 | 내용 |
|---|---|
| 헤더 | 💡 `AI Insight` + `[Live AI Scan]` 배지 + 대상 국가명 |
| 요약 문단 | 2~3문장. 예: `Mexico market shows rapid nearshoring expansion with an Export Gap of +15.4%p.` |
| 핵심 지표 칩 3개 | Export Gap, 전년대비 수입성장률(⬆️/⬇️ + %), 경쟁국 Top3 점유율 합계 |
| 추천 액션 | 관세·비관세 장벽 현황(C-1)을 반영한 진출 시 유의점 1~2줄 |
| 푸터 | `Target: Mexico (멕시코)` · `Predator Engine` |

- **생성 방식 (보류)**: AI 프롬프트/LLM 연동은 데이터 파이프라인(M1~M7) 완료 후 진행한다. 그 전에는 `pipeline/insight.py`가 고정 문구 또는 빈 상태(`데이터 분석 중…`)를 반환하는 stub이며, 이후 `insight.generate()`만 교체하면 되도록 인터페이스를 미리 고정한다.
- 갱신 시점: `selectedIso3`가 바뀔 때마다 재생성 (`GET /api/country/<iso3>/detail`의 `insight` 필드).

### 3.5 C-1 · Trade Barriers (관세율 · 비관세 장벽)

**위치**: Section C **좌측 컬럼 최상단** — AI Insight(Section B) 아래, Real-time Exchange Rate(C-5) 위. 기존 `Trade Show Schedule` 카드가 있던 자리를 대체한다 (Trade Show Schedule 컴포넌트는 삭제).

| 요소 | 명세 |
|---|---|
| 헤더 | `Trade Barriers` + 선택 국가 라벨 + `KITA TradeNavi` 배지 |
| 관세율 | 큰 숫자 `0.0%` + 유형 배지(`FTA` 협정세율 / `MFN` 최혜국세율) + 보조 문구 `한국산 HS {hs6} 적용세율`. 하단에 `관세 점수 9.5 / 10` (= `score_breakdown.tariff`) |
| 비관세 장벽 | `비관세 장벽 {n}건` + 항목 목록(최대 5개 표시, 초과 시 `+N건 더보기` 클릭으로 펼침). 0건이면 `확인된 비관세 장벽 없음` |
| 기준일 | 하단에 `조회일 2026-09-20` (`barriers.fetched_at`, 캐시 저장 시각) |
| 실패 상태 | 크롤링 실패 → ⚠️ `관세 정보를 불러오지 못했습니다 (관세 점수는 중립 처리)` |
| 환산 불가 | 종량세·복합세 등 %로 환산되지 않는 경우 → `종량세 등: 세율 환산 불가 (관세 점수는 중립 처리)` |
| 데이터 | `top20[].barriers` (§7.3) — **별도 API 호출 없음.** 후보 크롤링(Stage 3) 결과를 그대로 사용 |
| 갱신 | `target:selected` 시 선택 국가의 값으로 교체 |

- 비관세 장벽은 **점수에는 반영하지 않고 이 카드에서 표시만** 한다 (§5.4.1).
- 카드 높이는 좌측 컬럼에서 C-5와 나눠 채운다(§2.3 규칙 2).

### 3.6 C-5 · Real-time Exchange Rate (선택 국가 통화 ↔ KRW, 3년 전 vs 현재)

**핵심 인터랙션**: Top 20 표에서 국가를 클릭하면(= `target:selected`), 이 카드가 **해당 국가 통화 ↔ 원화(KRW)의 "3년 전 vs 현재" 비교 그래프**로 바뀐다. 지구본 점·타깃 칩·버블·`다음 타깃`으로 타깃이 바뀔 때도 동일하다.

이 카드가 보여주는 것은 환율 점수 5점의 근거인 **"3년 전보다 지금 환율이 한국 수출에 유리해졌나"** 이다. 3년치 일별 시계열이 아니라 **두 시점(오늘 / 정확히 3년 전 같은 날짜)** 의 환율만 사용한다 (§5.3).

| 요소 | 명세 |
|---|---|
| 헤더 | `Real-time Exchange Rate` + 비교쌍 라벨(예: `JPY ↔ KRW`) + **출처 배지** (`KEXIM`, 수출입은행 미고시 통화라 보조 소스를 쓴 경우 `yfinance`) |
| 요약 | 큰 글씨 `1 EUR = 1,540.2 KRW` + 기준일(예: `2026-09-18 고시`) |
| 비교 그래프 | **2점 라인 차트**: X = `3년 전 (2023-09-20)` / `현재 (2026-09-18)`, Y = KRW per 1 현지통화. 두 점을 선으로 잇고 각 점에 값 라벨. Y축은 두 값 주변으로 자동 스케일(막대가 아니라 점으로 그려 작은 변화도 보이게 함). 선 색은 유리(상승)/불리(하락)에 따라 §3.9.1의 ⬆️/⬇️ 색 규칙과 통일 |
| 변동 배지 | `+8.4%` (= `fx_change_3y_pct`) + 해석 문구: 상승 → `현지통화 강세 · 한국산 가격경쟁력 ↑`, 하락 → `현지통화 약세 · 한국산 가격경쟁력 ↓` |
| 점수 표시 | `환율 점수 3.8 / 5` (= `score_breakdown.fx_3y`) |
| 보조 행 | `USD/KRW 1,3xx` 한 줄 (헤더 USD/KRW 토글이 쓰는 값과 동일) |
| 데이터 | `top20[].fx` (§7.3) — **별도 API 호출 없음.** 분석(Stage 3)에서 이미 두 시점 환율을 구해 둠 |

**동작 규칙**

1. **방향 해석**: `KRW per 1 현지통화`가 오르면(= 원화 약세 / 현지통화 강세) 한국 수출에 유리하다. "원/달러 환율이 오르면 수출에 유리"라는 통상 해석과 같은 방향이다.
2. **기준일 표기**: 주말·공휴일·고시 전이면 직전 영업일 값을 쓰므로, 실제 사용된 날짜(`fx.now_date`, `fx.then_date`)를 그래프 X축과 요약에 그대로 표시한다.
3. 같은 통화를 쓰는 국가끼리 전환(예: 독일 → 이탈리아, 둘 다 EUR)하면 그래프는 그대로 유지된다.
4. USD 국가(미국 등)는 `USD ↔ KRW`로 표시한다.
5. **한국수출입은행이 고시하지 않는 통화**(MXN, VND, PLN 등)는 **yfinance로 자동 보완 조회**해 같은 형태의 그래프를 그린다. 이때 출처 배지를 `yfinance`로 바꾸고 `시세 종가 기준 (보조 소스)` 문구를 작게 붙인다. **두 소스 모두 실패한 경우에만** `이 통화의 환율 데이터를 불러올 수 없습니다 (환율 점수는 중립 처리)`를 표시하고, 점수는 중립값(0.5) + `data_flags: ["fx_missing"]`로 처리한다 (§5.3).
6. "Real-time"은 **당일 고시 기준**이다 (수출입은행은 영업일 오전 11시경 고시). 초 단위 실시간이 아니다.
7. 데이터 원천은 **한국수출입은행 오픈 API(주) → yfinance(보조)** 순서다 (§5.3). 소스가 달라도 그래프 형식·해석 문구는 동일하다.

### 3.7 C-2 · Global Blue Ocean Map (버블 차트)

| 항목 | 명세 |
|---|---|
| 차트 | Chart.js `bubble` |
| X축 | `Korea Penetration (%)` = 한국 점유율 (0~100) |
| Y축 | `Target Market Potential (0–100)` = 수요 잠재력 |
| 버블 크기 | 시장 규모(`market_size`)의 √ 스케일 |
| 색 | 선택된 타깃 = 빨강(`1순위 먹잇감`), 나머지 = 하늘색(`유망 사냥터`) |
| 해석 | **좌상단(낮은 점유율 · 높은 잠재력)일수록 블루오션.** 초안의 `Q1 포착` 라벨은 좌상단 사분면에 붙이고, 부제 문구도 "좌상단에 위치할수록…"으로 바로잡는다 (초안 문구는 "우상단"이라 되어 있어 실제 차트와 모순, §9 참고) |
| 인터랙션 | 버블 hover = 툴팁(국가, Score, 시장규모), 클릭 = 타깃 선택 |
| 데이터 | Top 20 전체 (`potential`, `korea_share_pct`, `market_size`) |

### 3.8 C-4 · Export Gap Trend in {Country}

| 항목 | 명세 |
|---|---|
| 차트 | 막대 + 선 혼합 (Chart.js `bar` + `line`, 이중 Y축) |
| 막대(왼쪽 축, USD) | `Total {Country} Import`(총수입), `Korea Export`(한국산 수입액) |
| 선(오른쪽 축, %) | `Export Gap` = 해당 연도의 `한국 세계 점유율 − 한국 점유율` (%p) |
| X축 | 최근 **10개 연도** (T−9 ~ T). 초안의 2012~2020은 목업 값이며 실제로는 T 기준 |
| 데이터 | `GET /api/country/<iso3>/detail`의 `gap_trend[]` |
| 캐시 주의 | 10개 연도 × 3계열(총수입·한국산·세계 한국점유율)이라 호출량이 크다. 국가 선택 시점에 **지연 로딩(lazy)** 하고 결과를 캐시 |

### 3.9 C-3 · Top 20 Blue Ocean Market Rankings (표)

**카드 헤더**: 제목 + 안내문(`행을 클릭하면 3D 지구본과 대시보드 해당 국가가 즉시 락온됩니다. (하드컷 1,000만$ → 간이점수 상위 50개국 중 최종 상위 20)`) + 정렬 드롭다운(`Score 순` / `한국 점유율 순` / `Growth 순` / `시장규모 순`).

**컬럼 정의 (변경 반영)**

| # | 컬럼 헤더 | 변경 | 표시 내용 | 데이터 필드 |
|---|---|---|---|---|
| 1 | `Rank` | 유지 | 순위 | `rank` |
| 2 | `Country` | 유지 | `MX Mexico` (ISO2 + 국가명) | `iso2`, `name_en` |
| 3 | `Score` | 유지 | 0~100 정수 표기(내부는 소수 1자리) | `score` |
| 4 | **`Growth 추세`** | `Potential` → 변경 | **⬆️ 또는 ⬇️ 기호만** 표시 | `growth.yoy_pct` |
| 5 | **`한국 점유율`** | `Penetration` → 변경 | `1.2%` | `korea_share_pct` |
| 6 | **`경쟁국`** | `경쟁국(Top3)` → `Top3` 텍스트 제거 | **Top 3 경쟁국 점유율 수치**(합계) 기본 표시 | `competitors.top3_share_pct` |
| 7 | `시장규모` | 유지 | `$1.84B` (USD/KRW 토글 반영) | `market_size_usd` |

선택된 행은 좌측 파란 바 + 연한 배경으로 하이라이트. 행 클릭 = 타깃 선택(§3.10).

#### 3.9.1 `Growth 추세` 컬럼 — ⬆️/⬇️ 표시와 클릭 인터랙션

**표시 규칙** (기준: 해당 국가의 해당 HS 품목 **전년대비 수입성장률** `yoy_pct = (수입액_T / 수입액_T-1 − 1) × 100`)

| 조건 | 표시 | aria-label |
|---|---|---|
| `yoy_pct > 0` (금액 증가) | ⬆️ (초록 계열) | `전년 대비 수입 증가` |
| `yoy_pct < 0` (금액 감소) | ⬇️ (빨강 계열) | `전년 대비 수입 감소` |
| `yoy_pct == 0` 또는 결측 | `–` (회색) | `증감 정보 없음` — 클릭 비활성 |

- 색만으로 구분하지 않도록 **기호 자체가 방향을 표현**한다 (색각 이상 접근성).
- 이 값은 점수 항목 '최근 1년 성장률'(§4)과 **동일한 원천 필드**를 쓴다. 표시와 점수가 서로 다른 수치를 보이면 안 된다.

**클릭 인터랙션**

1. 기호는 `<button type="button">`으로 렌더링한다 (키보드 Enter/Space 동작, 포커스 링).
2. 클릭하면 **팝오버(툴팁)** 가 기호 아래에 열린다:

```
전년 대비 수입 성장률
+12.3%
2023  $1.64B  →  2024  $1.84B
```

3. 닫힘: 같은 기호 재클릭 / 팝오버 밖 클릭 / `Esc`. **한 번에 팝오버 1개만** 열림(다른 것을 열면 기존 것은 닫힘).
4. 행 클릭(타깃 선택)과 충돌하지 않도록 기호 클릭에서 `event.stopPropagation()`.
5. 모바일: hover가 없으므로 위와 동일하게 탭으로 동작.
6. 팝오버 데이터는 `/api/analyze` 응답에 이미 포함(`growth.yoy_pct`, `growth.prev_value_usd`, `growth.curr_value_usd`, `growth.prev_year`, `growth.curr_year`) — **추가 API 호출 없음.**
7. 수치 포맷: 부호 포함(`+12.3%` / `-4.1%`), 소수 1자리. 금액은 USD/KRW 토글 반영.

#### 3.9.2 `경쟁국` 컬럼 — 점유율 수치와 클릭 인터랙션

**기본 표시**: Top 3 경쟁국의 **점유율 합계** 1개 수치 (예: `58.3%`). 컬럼 헤더에는 `Top3` 문구를 넣지 않는다.

- **"경쟁국"의 정의**: 타깃국의 해당 품목 수입 금액 상위 공급국 중 **한국을 제외한** 상위 3개국. (한국이 상위에 있으면 '한국 점유율'과 이중 반영되므로 제외 — §4.2 `top3_share`와 같은 값을 쓴다.)
- 점유율 분모는 타깃국의 해당 품목 **총수입액**.

**클릭 인터랙션**

1. 수치도 `<button type="button">`으로 렌더링 (밑줄 점선 등으로 "클릭 가능" 힌트).
2. 클릭하면 팝오버에 **국가 이름**이 표시된다:

```
경쟁국 (한국 제외)
1. 미국    32.1%
2. 중국    15.4%
3. 독일    10.8%
──────────────
합계       58.3%
```

3. 팝오버에는 **국가 이름 + 국가별 점유율**을 함께 표시한다 (확정).
4. 닫힘 규칙·단일 팝오버 규칙·`stopPropagation`·모바일 동작은 §3.9.1과 동일.
5. 데이터: `competitors.top3[] = [{iso3, name_ko, name_en, share_pct}]` (§7.3).

#### 3.9.3 팝오버 구현 메모

- Bootstrap 5 Popover를 쓸 경우 `data-bs-trigger="focus"`는 **Safari에서 button 클릭 시 포커스가 안 잡히는 문제**가 있으므로, `trigger: 'click'` + 문서 전체 클릭 리스너로 외부 클릭 시 닫기를 직접 구현한다.
- 팝오버 본문은 데이터 속성(`data-popover-html`)이 아니라 JS에서 응답 JSON으로 생성해 XSS 여지를 줄인다(국가명 등은 `textContent`로 삽입).

### 3.10 전역 상태 · 컴포넌트 연동

프론트는 단일 상태 객체를 둔다.

```js
const state = {
  hs6: "854140",        // 분석 품목 (헤더 검색창)
  selectedIso3: "MEX",  // 선택 타깃국
  currency: "USD",      // 표시 통화 토글
  sortBy: "score",      // Top 20 정렬 기준
  data: null            // /api/analyze 응답 (top20 등)
};
```

| 이벤트 | 트리거 | 갱신되는 컴포넌트 |
|---|---|---|
| `hs:changed` | 헤더 검색 제출 | 전체(로딩 스켈레톤 → 재렌더). `selectedIso3`는 새 1위로 리셋 |
| `target:selected` | 지구본 점 / 칩 / 표 행 / 버블 클릭 / `다음 타깃` | A-1 HUD, A-2 지구본 포커스, B AI Insight, C-1 관세·비관세 장벽, C-2 하이라이트, C-3 행 하이라이트, C-4 갭 추이, C-5 환율 비교 그래프(해당국 통화 ↔ KRW, 3년 전 vs 현재) |
| `currency:changed` | USD/KRW 토글 | 금액 표기 전부 (재요청 없음) |
| `sort:changed` | 정렬 드롭다운 | C-3 (재요청 없음, 클라이언트 정렬) |

---

## 4. 블루오션 점수(Score) 산정 — 100점 만점

### 4.1 배점표 (점수 배분표 이미지 기준)

| # | 지표 | 배점 | 무엇을 보는가 | 방향 | 데이터 소스 |
|---|---|---:|---|---|---|
| 1 | 전체 시장 규모 | 15 | 그 나라가 이 품목을 얼마나 수입하나 | 높을수록 좋음 | UN Comtrade |
| 2 | 최근 3년 성장률 | 15 | 시장이 계속 커지고 있나 | 높을수록 좋음 | UN Comtrade |
| 3 | 최근 1년 성장률 | 10 | 최근에도 성장세인가 | 높을수록 좋음 | UN Comtrade |
| 4 | 구글 트렌드 | 5 | 요즘 관심이 느는 중인가 | 높을수록 좋음 | **SerpAPI** |
| 5 | 3년 환율 변동 | 5 | 환율이 유리하게 움직였나 | 높을수록 좋음 | **한국수출입은행 API** (주) / **yfinance** (보조) |
| 6 | 한국 점유율 | 25 | 한국이 아직 못 판 여지가 있나 | **낮을수록 좋음** | UN Comtrade |
| 7 | 상위 3개국 점유율 | 15 | 소수 나라가 독점 중은 아닌가 | **낮을수록 좋음** | UN Comtrade |
| 8 | 관세율 | 10 | 수출할 때 세금을 얼마나 무나 | **낮을수록 좋음** | **KITA 트레이드내비 크롤링** (§5.4) |
| | **합계** | **100** | | | |

- 수요 측(1~5) 합계 **50점**, 공급 여지 측(6~8) 합계 **50점**.
- 이 표는 코드에서 `SCORE_SPEC` 하나로 관리하고, **점수 계산 · `평가기준(100점)` 모달 · `수식 명세` 모달**이 모두 이것을 참조한다 (문서/UI/코드 불일치 방지).

### 4.2 항목별 원지표(raw metric)와 정규화

최종 점수 = Σ (정규화 점수 `n_i` × 배점 `w_i`), 여기서 `n_i ∈ [0, 1]`.

| # | 원지표 (컬럼명) | 계산식 | 전처리 |
|---|---|---|---|
| 1 | `market_size` | `imp_T` (T년 총수입액, USD) | 편차가 커서 `log1p` 후 정규화 |
| 2 | `cagr3_pct` | `((imp_T / imp_T-3)^(1/3) − 1) × 100` | `imp_T-3 = 0`이면 결측. **절대평가**: 0% 미만 0점 / +30% 이상 만점 / 사이 선형 |
| 3 | `yoy_pct` | `(imp_T / imp_T-1 − 1) × 100` | `imp_T-1 = 0`이면 결측. **절대평가** (2번과 동일) |
| 4 | `trend_momentum` | 최근 13주 평균 ÷ 직전 39주 평균 (구글 트렌드 12개월 시계열) | 분모 0이면 결측. 트렌드 값은 검색어별 상대값(0~100)이라 **수준이 아니라 비율**로 국가 간 비교 |
| 5 | `fx_change_3y_pct` | `(현재 고시환율 ÷ 3년 전 같은 날짜 고시환율 − 1) × 100` (한국수출입은행 매매기준율, KRW per 1 현지통화, **두 시점만** 조회) | 현지통화가 원화 대비 **강세(= 원화 약세)** 면 한국 수출에 유리하므로 +. 수출입은행 미고시 통화는 **yfinance 보조 조회**, 두 소스 모두 실패해야 결측(중립 0.5) |
| 6 | `korea_share_pct` | `kor_T / imp_T × 100` | 낮을수록 좋으므로 `1 − n` |
| 7 | `top3_share_pct` | 한국 제외 상위 3개 공급국 수입액 합 ÷ `imp_T` × 100 | 낮을수록 좋으므로 `1 − n` |
| 8 | `tariff_rate_pct` | 타깃국이 한국산 해당 HS 품목에 부과하는 적용 관세율 (트레이드내비 크롤링, §5.4) | 낮을수록 좋으므로 `1 − n`. **FTA 협정세율이 있으면 우선**, 없으면 MFN. %로 환산 불가(종량세 등)면 결측 |

**정규화 방식 — 항목 성격에 따라 2가지를 쓴다**

**(A) 성장률 항목 (2번 3년, 3번 1년): 절대평가 — 후보 풀 분포와 무관하게 성장률 값 자체로 점수 산정**

- 성장률 `g`(%)가 **0% 미만(역성장)이면 무조건 0점.** 시장규모 하드컷(1,000만 달러)을 통과했더라도 예외 없음.
- **+30% 이상이면 무조건 만점.**
- **0% ~ 30% 구간은 비율에 따라 선형으로** 점수를 부여.

```
n = clip(g / 30, 0, 1)        # g < 0 → 0,  g >= 30 → 1,  그 사이는 g / 30
```

| 성장률 g | n | 3년 항목 (15점) | 1년 항목 (10점) |
|---:|---:|---:|---:|
| −12% | 0 | 0 | 0 |
| 0% | 0 | 0 | 0 |
| 7.5% | 0.25 | 3.75 | 2.5 |
| 15% | 0.5 | 7.5 | 5 |
| 30% | 1 | 15 | 10 |
| 48% | 1 | 15 | 10 |

- 2번 항목의 `g`는 3년 누적이 아니라 **3년 연평균 성장률(CAGR)** 이다. 같은 30% 기준을 적용한다.
- 이 기준은 **고정된 절대평가 규칙**이다. 후보 국가들의 분포나 실데이터에 맞춰 조정하지 않는다.
- 성장률이 결측(비교 연도의 수입액이 0이거나 미보고)이면 중립값 0.5 + `data_flags`.
- 역성장 국가도 후보에서 **제외하지는 않는다.** 성장률 항목만 0점을 받고, 한국 점유율(25점) 등 나머지 항목으로 순위가 정해진다.
- `Growth 추세` 컬럼의 ⬆️/⬇️는 여전히 `yoy_pct`의 **부호**로 결정한다(점수 규칙과 별개).

**(B) 그 외 항목 (1·4·5·6·7·8번): 후보 풀 상대 정규화 (min–max + 이상치 클리핑)**

```
x'   = clip(x, P5, P95)                 # 하·상위 5% 이상치 영향 제거 (후보 풀 기준)
n    = (x' − P5) / (P95 − P5)           # 0~1
n    = 1 − n                            # '낮을수록 좋음' 항목(6·7·8)만 반전
n    = 0.5                              # 결측이거나 P95 == P5인 경우 (중립값)
```

- (B)의 기준 집합은 **해당 단계의 후보 국가 풀**이다 → 그 품목의 후보들 사이에서의 상대 점수. 반면 (A) 성장률은 풀과 무관한 절대 규칙이다.
- 결측 항목은 중립값 0.5로 대체하되, 응답의 `data_flags`에 `["trend_missing"]` 등을 남겨 UI에서 ⚠️로 표시할 수 있게 한다.

### 4.3 파생 지표

| 지표 | 계산 |
|---|---|
| `score` | `Σ(n_i × w_i)` — 소수 1자리 |
| `potential` (수요 잠재력) | `Σ_{i=1..5}(n_i × w_i) / 50 × 100` |
| `export_gap_pp` | `korea_world_share_pct − korea_share_pct` |
| `korea_world_share_pct` | `KOR의 해당 HS 세계 수출액 ÷ 전 세계 해당 HS 수출액 합계 × 100` (품목당 1개 값) |

### 4.4 코드 스펙 (단일 원천)

```python
# blueocean/pipeline/scoring.py
import numpy as np
import pandas as pd


SCORE_SPEC = [
    # key          label               weight column              higher_better transform fixed_range               side
    dict(key="market_size", label="전체 시장 규모",    weight=15, column="market_size",      higher_is_better=True,  transform="log1p", fixed_range=None,                   side="demand"),
    dict(key="growth_3y",   label="최근 3년 성장률",   weight=15, column="cagr3_pct",        higher_is_better=True,  transform=None,    fixed_range=(0, 30),                 side="demand"),
    dict(key="growth_1y",   label="최근 1년 성장률",   weight=10, column="yoy_pct",          higher_is_better=True,  transform=None,    fixed_range=(0, 30),                 side="demand"),
    dict(key="trend",       label="구글 트렌드",       weight=5,  column="trend_momentum",   higher_is_better=True,  transform=None,    fixed_range=None,                   side="demand"),
    dict(key="fx_3y",       label="3년 환율 변동",     weight=5,  column="fx_change_3y_pct", higher_is_better=True,  transform=None,    fixed_range=None,                   side="demand"),
    dict(key="korea_share", label="한국 점유율",       weight=25, column="korea_share_pct",  higher_is_better=False, transform=None,    fixed_range=None,                   side="supply"),
    dict(key="top3_share",  label="상위 3개국 점유율", weight=15, column="top3_share_pct",   higher_is_better=False, transform=None,    fixed_range=None,                   side="supply"),
    dict(key="tariff",      label="관세율",            weight=10, column="tariff_rate_pct",  higher_is_better=False, transform=None,    fixed_range=None,                   side="supply"),
]
assert sum(s["weight"] for s in SCORE_SPEC) == 100


def normalize(s: pd.Series, higher_is_better: bool = True, transform: str | None = None,
              fixed_range: tuple[float, float] | None = None,
              lo_q: float = 0.05, hi_q: float = 0.95) -> pd.Series:
    # 0~1 정규화. 결측이면 중립값 0.5.
    x = s.astype(float).replace([np.inf, -np.inf], np.nan)

    # (A) 절대평가: lo 이하(역성장 포함) 0점, hi 이상 만점, 사이는 선형. 후보 풀과 무관.
    if fixed_range is not None:
        lo, hi = fixed_range
        n = ((x - lo) / (hi - lo)).clip(0, 1)
        return n if higher_is_better else 1 - n
        # (NaN은 score()에서 0.5로 대체)

    # (B) 후보 풀 상대 정규화: min-max + P5~P95 클리핑
    if transform == "log1p":
        x = np.log1p(x.clip(lower=0))
    lo, hi = x.quantile(lo_q), x.quantile(hi_q)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return pd.Series(np.nan, index=s.index)          # 분산 0 → 전부 중립
    n = (x.clip(lo, hi) - lo) / (hi - lo)
    return n if higher_is_better else 1 - n


def score(df: pd.DataFrame, keys: list[str] | None = None) -> pd.DataFrame:
    # keys를 주면 해당 항목만으로 계산 후 100점으로 재환산(간이 점수용).
    specs = [s for s in SCORE_SPEC if keys is None or s["key"] in keys]
    out = df.copy()
    for s in specs:
        n = normalize(out[s["column"]], s["higher_is_better"], s["transform"], s["fixed_range"])
        out[f"n_{s['key']}"] = n.fillna(0.5)             # 결측/분산 0 → 중립값 0.5
        out[f"pt_{s['key']}"] = out[f"n_{s['key']}"] * s["weight"]
    w_total = sum(s["weight"] for s in specs)
    out["score"] = (out[[f"pt_{s['key']}" for s in specs]].sum(axis=1) / w_total * 100).round(1)

    demand = [s for s in specs if s["side"] == "demand"]
    if demand:
        d_total = sum(s["weight"] for s in demand)
        out["potential"] = (out[[f"pt_{s['key']}" for s in demand]].sum(axis=1) / d_total * 100).round(1)
    return out
```

> `keys=None`이면 `w_total = 100`이라 위 점수식과 동일하다. `keys`를 준 간이 점수는 깔때기 2단계에서만 쓴다 (§6.3).

---

## 5. 외부 API 연동

모든 외부 호출은 `blueocean/services/` 아래 **클라이언트 모듈 1개씩**에 격리하고, 파이프라인은 그 모듈의 반환 DataFrame만 다룬다. API 키는 `.env`에서 읽는다. 데이터 소스는 **UN Comtrade · SerpAPI · 한국수출입은행 오픈 API(환율 주 소스) · yfinance(환율 보조 소스)** 와 **KITA 트레이드내비(크롤링, §5.4)** 이다.

```
COMTRADE_API_KEYS=key1,key2,key3   # 쉼표 구분 키 풀 (§5.1)
SERPAPI_KEY=...
KEXIM_API_KEY=...                  # 한국수출입은행 오픈 API 인증키 (§5.3)
# yfinance(환율 보조)는 키가 필요 없음
```

> ⚠️ 아래 엔드포인트·파라미터명은 구현 시점에 **각 공식 문서로 재확인**할 것. 요금제·호출 한도·과거 데이터 제공 여부는 플랜에 따라 다르다.

### 5.1 UN Comtrade API — 베이스 데이터

| 항목 | 내용 |
|---|---|
| 역할 | 국가별 수입 금액, 한국산 수입 금액, 공급국별 수입 금액, 세계 수출 금액 → 시장 규모·성장률·한국 점유율·Top3·Export Gap 전부의 원천 |
| 주요 파라미터 | `reporterCode`(보고국), `partnerCode`(상대국), `period`(연도), `cmdCode`(HS6), `flowCode`(`M`=수입, `X`=수출), 구독키 |
| 자주 쓰는 코드 | 한국 `410`, 전 세계 `0`, 멕시코 `484`, 베트남 `704`, 폴란드 `616`, 인도 `356`, 독일 `276` (UN 숫자 코드) |
| 응답 핵심 필드 | `reporterCode`, `reporterISO`, `partnerCode`, `partnerISO`, `period`, `cmdCode`, `primaryValue`(USD) |
| 주의 | ① 연간 데이터는 **1~2년 지연**되고 국가별 보고 시점이 다르다 ② 집계용 파트너(`World`, `Areas nes` 등)는 실제 국가가 아니므로 화이트리스트(`country_codes.csv`)로 걸러야 한다 ③ 무료 키는 호출 수/레코드 수 제한이 있다. **여러 계정의 키를 키 풀(`COMTRADE_API_KEYS`)로 로테이션**(요청마다 라운드로빈, 429·한도 응답 시 다음 키로 전환)하고 캐시도 병행한다. 계정 다중 사용이 Comtrade 이용약관상 문제없는지는 확인해 둘 것 ④ HS 개정판이 연도별로 다를 수 있으니 6자리 기준으로 통일 |

**호출 레시피 (품목 1개 분석 시)**

| # | 호출 | 얻는 것 | 횟수 |
|---|---|---|---|
| ① | `reporter=all, partner=0(World), flow=M, years=[T-3,T-1,T]` | 각국 총수입 (시장규모, 성장률) | 1~3 |
| ② | `reporter=all, partner=410(Korea), flow=M, years=[T-3,T-1,T]` | 각국의 한국산 수입 (한국 점유율) | 1~3 |
| ③ | `reporter=410, partner=0, flow=X, year=T` + `reporter=all, partner=0, flow=X, year=T` | 한국 세계 점유율 (Export Gap의 기준값) | 2 |
| ④ | `reporter=<iso>, partner=all, flow=M, year=T` — **상위 50개국만** | 공급국별 수입 → Top 3 경쟁국 | ≤ 50 |
| ⑤ | 국가 선택 시: 위 ①②③을 T-9~T로 확장 | C-4 갭 추이 | 온디맨드 |

### 5.2 SerpAPI — 구글 트렌드

| 항목 | 내용 |
|---|---|
| 역할 | 타깃국의 구글 검색 관심도 추세 → 점수 항목 4번 `trend_momentum` (5점) |
| 호출 | Google Trends 엔진, `q`(검색어), `geo`(국가 ISO2), 기간 `today 12-m`, 시계열(TIMESERIES) 요청 |
| 검색어 | `data/hs_keyword_map.csv` (`hs6, keyword_en, keyword_local`)로 HS코드→검색어 매핑. v1은 영어 검색어 1개, 국가별 현지어는 선택 확장 |
| 처리 | 응답의 주간 시계열 → `trend_momentum = mean(최근 13주) / mean(직전 39주)` |
| 호출 절약 | 호출당 과금·한도가 있으므로 **정밀 점수 단계의 상위 50개국에만** 호출 (§6.3). 결과는 `(hs6, iso2)` 키로 7일 캐시 |
| 실패 처리 | 한도 초과·검색량 부족(전부 0)·오류 → 결측 처리(중립 0.5) + `data_flags`에 `trend_missing` |

### 5.3 환율 — 한국수출입은행 오픈 API(주) + yfinance(Fallback)

환율 점수(5점)가 알고 싶은 것은 **"3년 전보다 지금 환율이 한국 수출에 유리하게 움직였나"** 하나뿐이다. 그래서 3년치 일별 데이터가 필요 없고, **오늘 / 정확히 3년 전 같은 날짜, 두 시점**만 조회한다.

> "수출입은행아, 오늘(2026-09-20) 미국 환율 얼마야?"
> "수출입은행아, 딱 3년 전(2023-09-20) 미국 환율 얼마였어?"

#### 5.3.1 소스 우선순위와 Fallback 원칙

| 순위 | 소스 | 대상 |
|---|---|---|
| 1 (주) | **한국수출입은행 오픈 API** | 수출입은행이 고시하는 통화 (USD, EUR, JPY, CNH, GBP …) |
| 2 (보조) | **yfinance** | 수출입은행이 고시하지 않는 통화 (MXN, VND, PLN, INR 등). 수출입은행 호출 자체가 실패한 경우에는 전 통화 |
| 3 | 결측 처리 | 두 소스 모두 실패한 통화만. 환율 점수 중립(0.5) + `fx_missing` |

- **에러를 밖으로 던지지 않는다.** 소스 호출은 모두 `try / except`로 감싸서, 실패하면 로그만 남기고 다음 순위로 넘어간다. 환율 때문에 분석 전체가 중단되는 일은 없다.
- 소스 하나에서 다음 소스로 넘어가는 단위는 **통화 단위**다 (수출입은행이 고시하는 통화는 그대로 수출입은행 값을 쓰고, 미고시 통화만 yfinance로 보완).
- 어느 소스를 썼는지는 응답의 `fx.source`(`"KEXIM"` / `"yfinance"`)와 `data_flags`(`fx_fallback_yfinance`)에 남기고, C-5 카드에 출처 배지로 표시한다 (§3.6).

#### 5.3.2 주 소스 — 한국수출입은행 오픈 API

| 항목 | 내용 |
|---|---|
| 방식 | `requests`로 한국수출입은행 오픈 API(현재환율) 호출. **인증키 필요** (`KEXIM_API_KEY`) |
| 엔드포인트 | `https://www.koreaexim.go.kr/site/program/financial/exchangeJSON` — 파라미터 `authkey`, `searchdate`(YYYYMMDD), `data=AP01`(환율). ⚠️ 구현 시 공식 문서로 재확인 |
| 응답 | 통화별 행. `cur_unit`(예: `USD`, `JPY(100)`), `cur_nm`(통화명), `deal_bas_r`(매매기준율, 쉼표 포함 문자열) 등. **날짜 1건 조회로 전 통화**를 한 번에 받는다 |
| 조회 횟수 | 분석 1회당 **2번**(오늘 / 3년 전 같은 날짜). 영업일 보정이 필요하면 몇 번 추가. 후보 국가 수와 무관 |
| 영업일 보정 | 주말·공휴일·고시 전(영업일 오전 11시경 이전)에는 빈 응답 → **직전 영업일로 최대 7일 거슬러** 조회. 실제 사용된 날짜를 `now_date`, `then_date`로 남겨 UI에 표시 |
| 단위 통일 | `JPY(100)`처럼 100단위로 고시되는 통화는 `deal_bas_r ÷ 100`으로 **1단위당 원화**로 맞춘다 |
| 통화 코드 | 위안화는 `CNH`로 고시된다 → 내부 통화코드 `CNY`를 `CNH`로 매핑 |
| 3년 전 날짜 | `오늘 − 3년` (`pd.DateOffset(years=3)`). 2월 29일 등은 라이브러리가 보정 |
| 점수 입력값 | `fx_change_3y_pct = (현재 ÷ 3년 전 − 1) × 100`, 단위는 KRW per 1 현지통화. `+` = 현지통화 강세(원화 약세) = 한국 수출에 유리 |

#### 5.3.3 보조 소스 — yfinance (Fallback)

| 항목 | 내용 |
|---|---|
| 라이브러리 | `yfinance` (키·가입 불필요). **Fallback이 실제로 필요할 때만 import**해서 평소에는 로드하지 않는다 |
| 발동 조건 | ① 후보 통화 중 수출입은행 응답에 없는 통화(MXN, VND, PLN, INR 등) ② 수출입은행 호출이 전부 실패(네트워크·인증·빈 응답)한 경우의 전 통화 |
| 티커 | `USD{통화코드}=X` (1달러당 해당 통화, 예: `USDMXN=X`, `USDVND=X`)와 `USDKRW=X` |
| 계산 | `KRW per 1 현지통화 = USDKRW=X ÷ USD{통화}=X`. **원화·현지통화 모두 Yahoo 종가로 계산**해 내부 일관성을 유지한다 (수출입은행 매매기준율과 섞지 않음) |
| 두 시점 | 오늘(최신 종가) / 3년 전 같은 날짜. 그날 종가가 없으면 **직전 거래일**(최대 10일 전까지 조회 창) |
| 호출 방식 | 미고시 통화 전부를 티커 리스트로 묶어 **배치 조회 × 2회**(현재 / 3년 전). 통화 수와 무관하게 호출 수 일정 |
| 결과 표기 | `fx.source = "yfinance"`, `data_flags: ["fx_fallback_yfinance"]` (정보용 플래그, 결측 아님) |
| 캐시 | `ttl_cache` 24시간(키 = 통화 목록 + 날짜). **빈 결과·실패는 캐시하지 않음** |

**주의 · 한계**

1. yfinance는 Yahoo Finance 데이터를 가져오는 **비공식 라이브러리**라 SLA가 없다. 호출이 과하면 429/일시 차단이 생길 수 있고 버전 업데이트로 반환 형식이 바뀔 수 있다 → `requirements.txt`에서 **버전 고정**, 배치 조회, 캐시, 그리고 아래 `try / except`로 대응한다. (Fallback 전용이라 평소 호출량은 미고시 통화 국가가 후보에 있을 때만 발생)
2. 일부 통화는 Yahoo 티커가 없거나 데이터가 끊길 수 있다 → 그 통화는 `fx_missing`(중립 0.5). M6에서 `country_codes.csv`의 전 통화에 대해 **수출입은행 고시 여부 / Yahoo 티커 존재 여부**를 점검하는 스크립트를 먼저 돌린다.
3. 시세 소스가 달라(수출입은행 매매기준율 vs Yahoo 종가) 절대값은 약간 다를 수 있다. 점수는 **같은 소스 안에서의 3년 전 대비 변동률**만 쓰므로 영향이 작다.
4. 명목환율이라 물가 상승은 반영하지 않는다 (고인플레이션 국가는 해석 주의).
5. 서비스를 외부에 공개·상용화하는 경우 Yahoo 데이터 이용 조건을 확인한다.

#### 5.3.4 코드 (Try-Except Fallback 포함)

```python
# blueocean/services/fx.py
import logging
import re

import pandas as pd
import requests

from .. import config
from .cache import ttl_cache

log = logging.getLogger(__name__)
KEXIM_URL = "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
ALIAS = {"CNY": "CNH"}            # 수출입은행은 위안화를 CNH로 고시


# ── 1) 주 소스: 한국수출입은행 ─────────────────────────────────────────
@ttl_cache(ttl=24 * 3600, cache_if=lambda r: bool(r))       # 빈 응답(휴일·고시 전)은 캐시하지 않음
def _kexim_day(yyyymmdd: str) -> dict:
    # 해당일 고시환율 {통화코드: 1단위당 원화}. 주말·공휴일·고시 전이면 빈 dict.
    resp = requests.get(KEXIM_URL, timeout=10,
                        params={"authkey": config.KEXIM_API_KEY, "searchdate": yyyymmdd, "data": "AP01"})
    resp.raise_for_status()
    out = {}
    for row in resp.json() or []:
        if "cur_unit" not in row:                            # 인증 오류 등 결과코드만 온 경우
            continue
        m = re.match(r"([A-Z]+)(?:\((\d+)\))?", row["cur_unit"])          # 'JPY(100)' -> JPY, 100
        if not m:
            continue
        code, unit = m.group(1), int(m.group(2) or 1)
        out[code] = float(str(row["deal_bas_r"]).replace(",", "")) / unit  # 매매기준율, 1단위당 원화
    return out


def _kexim_on_or_before(day: pd.Timestamp, max_back: int = 7) -> tuple[pd.Timestamp, dict]:
    # 해당일 고시가 없으면 직전 영업일로 최대 max_back일 거슬러 올라간다.
    for k in range(max_back + 1):
        d = day - pd.Timedelta(days=k)
        try:
            rates = _kexim_day(d.strftime("%Y%m%d"))
        except (requests.RequestException, ValueError, KeyError) as e:     # 네트워크·인증·JSON 오류
            log.warning("KEXIM 조회 실패(%s): %s -> yfinance fallback으로 전환", d.date(), e)
            return day, {}                                                  # 더 거슬러 가도 같은 오류 -> 포기
        if rates:
            return d, rates
    return day, {}


# ── 2) 보조 소스: yfinance (수출입은행 미고시 통화용) ─────────────────────
def _yf_close(tickers: list, day: pd.Timestamp):
    import yfinance as yf                                   # 지연 import: fallback이 필요할 때만 로드
    raw = yf.download(tickers, start=day - pd.Timedelta(days=10), end=day + pd.Timedelta(days=1),
                      interval="1d", auto_adjust=False, progress=False)["Close"]
    if isinstance(raw, pd.Series):                          # 티커 1개일 때 반환 형식 차이 흡수
        raw = raw.to_frame(tickers[0])
    raw = raw.dropna(how="all")
    if raw.empty:
        return None, {}
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.index[-1], raw.ffill().iloc[-1].dropna().to_dict()          # (실제 사용된 날짜, {티커: 종가})


@ttl_cache(ttl=24 * 3600, cache_if=lambda r: bool(r))       # 빈 결과는 캐시하지 않음
def _yf_two_points(ccys: tuple, now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    tickers = ["USDKRW=X"] + [f"USD{c}=X" for c in ccys]                   # 배치 조회 (통화 수와 무관하게 2회)
    now_d, now = _yf_close(tickers, now_day)
    then_d, then = _yf_close(tickers, then_day)
    out = {}
    for c in ccys:
        k = f"USD{c}=X"
        if all(x in px for px in (now, then) for x in ("USDKRW=X", k)):    # 티커가 없는 통화는 빠짐
            out[c] = {"now": now["USDKRW=X"] / now[k], "then": then["USDKRW=X"] / then[k],
                      "now_date": now_d, "then_date": then_d}              # KRW per 1 현지통화
    return out


def _fallback(ccys: list, now_day: pd.Timestamp, then_day: pd.Timestamp) -> dict:
    if not ccys:
        return {}
    try:
        return _yf_two_points(tuple(sorted(ccys)), now_day, then_day)
    except Exception as e:                                  # yfinance는 429·형식 변경 등 예외 종류가 다양 -> 전부 흡수
        log.warning("yfinance fallback 실패(%s): %s", sorted(ccys), e)
        return {}                                           # 에러를 던지지 않고 결측(중립 0.5)으로 넘어감


# ── 3) 통합: 통화별로 주 소스 -> 보조 소스 -> 결측 ─────────────────────────
def snapshot() -> dict:
    # 오늘과 정확히 3년 전 같은 날짜, 딱 두 시점의 수출입은행 전 통화 환율.
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    then_target = today - pd.DateOffset(years=3)
    now_d, now = _kexim_on_or_before(today)
    then_d, then = _kexim_on_or_before(then_target)
    return {"today": today, "then_target": then_target,
            "now_date": now_d, "then_date": then_d, "now": now, "then": then}


def change_3y_krw(currency_codes: pd.Series) -> pd.DataFrame:
    # 후보국 통화코드 Series(index=iso3) -> 3년 환율 변동과 C-5용 값. 점수 항목 5번의 입력.
    snap = snapshot()
    has_kexim = lambda c: bool(snap["now"].get(ALIAS.get(c, c))) and bool(snap["then"].get(ALIAS.get(c, c)))
    need_fb = [c for c in currency_codes.dropna().unique() if c != "KRW" and not has_kexim(c)]
    fb = _fallback(need_fb, snap["today"], snap["then_target"])   # 미고시 통화만 yfinance (실패해도 예외 없음)

    rows = []
    for ccy in currency_codes:
        n = t = nd = td = src = None
        if pd.notna(ccy) and has_kexim(ccy):                       # 주 소스
            k = ALIAS.get(ccy, ccy)
            n, t, nd, td, src = snap["now"][k], snap["then"][k], snap["now_date"], snap["then_date"], "KEXIM"
        elif ccy in fb:                                            # 보조 소스
            f = fb[ccy]
            n, t, nd, td, src = f["now"], f["then"], f["now_date"], f["then_date"], "yfinance"
        ok = bool(n) and bool(t)                                   # 두 소스 모두 실패면 False -> 중립 0.5
        rows.append({
            "fx_change_3y_pct": (n / t - 1) * 100 if ok else float("nan"),
            "krw_per_local_now": n if ok else None, "krw_per_local_then": t if ok else None,
            "fx_now_date": nd.date().isoformat() if ok else None,
            "fx_then_date": td.date().isoformat() if ok else None,
            "fx_source": src if ok else None,                      # "KEXIM" | "yfinance" | None
            "fx_ok": ok,
        })
    return pd.DataFrame(rows, index=currency_codes.index)
```

> `/api/fx/latest`(헤더 USD/KRW 토글)는 `snapshot()["now"]["USD"]`를 반환하고, 수출입은행 호출이 실패하면 yfinance `USDKRW=X` 최신 종가로 대체한다. C-5 그래프는 별도 API 없이 `/api/analyze` 응답의 `top20[].fx`를 그대로 쓰므로, **그래프의 변동률과 점수 입력값이 항상 같은 값**이다.

### 5.4 KITA 트레이드내비(TradeNavi) — 관세율 · 비관세 장벽 실시간 크롤링

점수 항목 8번 `관세율(10점)`과 비관세 장벽 정보의 원천이다. 별도 공식 API 대신 **트레이드내비 화면이 내부적으로 호출하는 XHR(Fetch) 엔드포인트를 백엔드 `requests`로 직접 호출**한다.

#### 5.4.1 동작 개요

| 항목 | 명세 |
|---|---|
| 트리거 | 사용자가 대시보드에서 HS Code를 검색하면(`GET /api/analyze?hs=`) 깔때기 **Stage 3(상위 50개 후보)** 에서 백엔드가 실시간으로 호출. 후보 국가마다 요청 1건 |
| 요청 방식 | `requests` (Session 유지). Payload(데이터 폼)에 **사용자가 입력한 HS Code와 국가 코드를 동적 변수로 삽입** |
| 추출 결과 | ① `tariff_rate_pct` — 한국산에 적용되는 관세율(%) ② `tariff_type` — `FTA`(협정세율) / `MFN`(최혜국세율) 등 ③ `ntb_items` — 비관세 장벽 항목 목록 |
| 관세율 선택 규칙 | 한국산에 적용되는 **협정세율(FTA)이 있으면 우선**, 없으면 MFN 세율. 종량세·복합세처럼 %로 환산되지 않는 경우는 결측 처리 + `data_flags: ["tariff_non_advalorem"]` |
| 점수 반영 | `tariff_rate_pct`만 점수 8번(10점, 낮을수록 좋음)에 반영. **비관세 장벽은 점수에 넣지 않고 표시 전용**(C-1 카드 §3.5, 데이터는 §7.3 `barriers`). 점수에 넣으려면 배점 재설계가 필요 |
| 캐시 | `(hs6, 국가코드)` 키로 **TTL 7일** 캐시. 같은 품목·국가는 재요청하지 않는다 (§5.4.4) |

> ⚠️ **엔드포인트 URL, HTTP 메서드, Payload 필드명, 국가 코드 체계, 응답 포맷(JSON/HTML)은 아직 실측되지 않았다.** 브라우저 개발자도구(Network → Fetch/XHR)에서 캡처한 값을 **팀이 `config.py`에 수동으로 입력한다(추후).** 아래 코드의 `<<실측>>` 표시가 그 자리이며, 입력 전에는 크롤러가 실패(`ok=False`)로 처리해 관세 점수가 중립(0.5)이 된다.

#### 5.4.2 요청 구성

```python
# config.py (실측 후 채움)
TRADENAVI_URL      = "<<실측: XHR 엔드포인트 URL>>"
TRADENAVI_REFERER  = "<<실측: 해당 조회 화면 URL>>"
TRADENAVI_METHOD   = "POST"                          # <<실측 확인>>
# Payload 템플릿: {hs}, {country}가 요청 시점에 사용자 입력값으로 치환된다.
TRADENAVI_PAYLOAD_TEMPLATE = {
    "<<실측: HS코드 필드명>>":  "{hs}",              # HS 자릿수·하이픈 형식(6자리/10자리)도 실측 확인
    "<<실측: 국가코드 필드명>>": "{country}",
    # ... 그 외 화면이 함께 보내는 고정 필드는 그대로 복사
}
```

- **국가 코드 매핑**: 트레이드내비가 쓰는 국가 코드를 `country_codes.csv`에 `tradenavi_code` 컬럼으로 추가한다 (`iso3 → tradenavi_code`).
- **HS 형식**: 분석은 6자리 기준이지만 트레이드내비가 더 긴 자리(예: 10자리)를 요구하면, 6자리로 조회 가능한지 먼저 확인하고 불가하면 대표 세번을 선택하는 규칙을 별도로 정한다.

#### 5.4.3 헤더 위장 · 요청 예절

크롤링 차단을 피하기 위해 **브라우저가 보내는 헤더를 그대로 흉내 낸다.**

| 헤더 | 값 |
|---|---|
| `User-Agent` | 최신 Chrome/Edge 데스크톱 UA. 3~5개를 풀로 두고 세션 단위로 랜덤 선택 |
| `Accept` | `application/json, text/javascript, */*; q=0.01` (실측한 요청과 동일하게) |
| `Accept-Language` | `ko-KR,ko;q=0.9,en-US;q=0.8` |
| `X-Requested-With` | `XMLHttpRequest` (XHR 요청이면) |
| `Referer` | 해당 조회 화면 URL (`TRADENAVI_REFERER`) |
| `Origin`, `Content-Type` | 실측한 값 그대로 (POST 폼이면 `application/x-www-form-urlencoded; charset=UTF-8`) |

- **쿠키/세션**: `requests.Session()`으로 Referer 화면을 먼저 1회 GET해 세션 쿠키를 받은 뒤 XHR을 호출한다(필요한 경우).
- **속도 제한**: 요청 사이에 0.4~1.2초 랜덤 지연, 동시 요청은 최대 4개(`ThreadPoolExecutor`). 403/429 응답이면 지수 백오프(2초, 4초…) 후 최대 3회 재시도.
- 헤더 위장은 차단 가능성을 낮출 뿐 보장하지 않는다. **캐시로 호출 수 자체를 줄이는 것이 1차 방어**다.
- 운영 전에 트레이드내비의 이용약관·`robots.txt`와 서비스 공개 범위(내부용/외부 공개)를 확인해 둘 것.

#### 5.4.4 캐싱 (Streamlit `@st.cache_data` → Flask 대응)

`@st.cache_data`는 Streamlit 전용이라, 현재 스택(Flask)에서는 **같은 역할을 하는 TTL 캐시 데코레이터**를 `services/cache.py`에 두고 동일하게 쓴다. (Flask-Caching의 `@cache.memoize(timeout=…)`으로 대체해도 된다. 기존 크롤러를 Streamlit에서 프로토타이핑했다면 데코레이터만 교체해 이식하면 된다.)

```python
# blueocean/services/cache.py
import functools, threading, time

_store, _lock = {}, threading.Lock()

def ttl_cache(ttl: int, cache_if=lambda r: True):
    # 인자 기준으로 결과를 ttl초 동안 캐시. cache_if가 False면(예: 크롤링 실패) 캐시하지 않는다.
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args):
            key = (fn.__qualname__, args)
            now = time.time()
            with _lock:
                hit = _store.get(key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            result = fn(*args)
            if cache_if(result):
                with _lock:
                    _store[key] = (now, result)
            return result
        return wrapper
    return deco
```

- 서버 재시작 후에도 살리려면 결과를 JSON/Parquet 파일(`data/cache/tariff/`)에도 기록한다(§6.4).
- **실패 응답은 캐시하지 않는다.** 그래야 일시 차단 후 다음 요청에서 재시도된다.

#### 5.4.5 크롤러 코드 골격

```python
# blueocean/services/tariff.py
import random, time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from .. import config
from .cache import ttl_cache

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config.TRADENAVI_REFERER,
    })
    try:
        s.get(config.TRADENAVI_REFERER, timeout=10)      # 세션 쿠키 확보 (필요한 경우)
    except requests.RequestException:
        pass
    return s


def _parse(resp: requests.Response) -> dict:
    # <<실측 후 구현>> 응답(JSON 또는 HTML 조각)에서 아래 세 값만 뽑아 정규화한다.
    #   tariff_rate_pct : float | None   (한국산 적용세율, 협정세율 우선)
    #   tariff_type     : "FTA" | "MFN" | ...
    #   ntb_items       : list[str]      (비관세 장벽 항목명/요약)
    raise NotImplementedError


@ttl_cache(ttl=7 * 24 * 3600, cache_if=lambda r: r["ok"])
def _fetch_one(hs6: str, country_code: str) -> dict:
    if "<<" in config.TRADENAVI_URL:                                    # 실측값 입력 전 -> 실패로 처리
        return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}
    payload = {k: v.format(hs=hs6, country=country_code)
               for k, v in config.TRADENAVI_PAYLOAD_TEMPLATE.items()}   # HS·국가코드를 동적 삽입
    session = _new_session()
    for attempt in range(3):
        time.sleep(random.uniform(0.4, 1.2))                            # 요청 간 랜덤 지연
        try:
            resp = session.request(config.TRADENAVI_METHOD, config.TRADENAVI_URL,
                                   data=payload, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code in (403, 429):                              # 차단·과호출 → 백오프 후 재시도
            time.sleep(2 ** (attempt + 1))
            continue
        if resp.ok:
            try:
                return {"ok": True, "fetched_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat(timespec="seconds"), **_parse(resp)}
            except (KeyError, ValueError, NotImplementedError):
                break                                                   # 응답 구조 변경 의심 -> 결측 처리
    return {"ok": False, "fetched_at": None, "tariff_rate_pct": None, "tariff_type": None, "ntb_items": []}


def fetch_barriers(hs6: str, cand: pd.DataFrame, workers: int = 4) -> pd.DataFrame:
    # 후보국(index=iso3, 컬럼 tradenavi_code 필요) 전체의 관세율·비관세장벽을 조회해 DataFrame으로 반환.
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda c: _fetch_one(hs6, c), cand["tradenavi_code"]))
    return pd.DataFrame({
        "tariff_rate_pct": [r["tariff_rate_pct"] for r in results],   # 실패 시 None → 점수에서 중립 0.5
        "tariff_type":     [r["tariff_type"] for r in results],
        "ntb_items":       [r["ntb_items"] for r in results],
        "ntb_count":       [len(r["ntb_items"]) for r in results],
        "tariff_ok":       [r["ok"] for r in results],
        "tariff_fetched_at": [r["fetched_at"] for r in results],
    }, index=cand.index)
```

- `tariff_ok == False`인 국가는 응답의 `data_flags`에 `"tariff_missing"`을 남기고, 점수 8번은 중립값(0.5)으로 처리한다(§6.5).
- 50개국 첫 조회는 지연·동시성 제한 때문에 **십수 초**가 걸릴 수 있다 → `/api/analyze`의 비동기 잡(`job_id`) 구조(§6.5)로 흡수하고, 이후 같은 품목·국가는 캐시에서 즉시 반환된다.

---

## 6. 데이터 파이프라인 (Pandas)

### 6.1 처리 흐름 개요 (깔때기 방식)

```
HS6 입력
  │
  ▼
[Stage 0] 입력 검증·정규화 ── hs6 = "854140"
  │
  ▼
[Stage 1] 벌크 수집 (Comtrade ①②③)  ─────────►  df_market  (전 세계 국가 × 지표)
  │       하드컷: 시장규모 ≥ 10,000,000 USD (1,000만 달러)
  │       1차 사냥 필터: export_gap_pp > 0
  │       제외: 한국, 집계 파트너
  ▼
[Stage 2] 간이 점수 (Comtrade 항목만: 1,2,3,6) ─► 상위 50개국  df_candidates
  │
  ▼
[Stage 3] 정밀 점수: Top3(④) + 구글트렌드 + 환율 + 관세(트레이드내비 크롤링) 추가 → 8항목 100점
  │
  ▼
[Stage 4] 정렬 → 상위 20개 + 표시용 필드 조립  ─► df_top20 ─► JSON (/api/analyze)
```

이 구조 덕분에 호출이 무거운 항목(④ 공급국별 수입, SerpAPI, 환율 이력)은 **최종 후보 50개국에만** 실행된다.

### 6.2 기준 연도 T 결정

```python
def pick_base_year(imports_long: pd.DataFrame, coverage: float = 0.8) -> int:
    """수입액 기준으로 coverage 이상의 국가가 보고한 가장 최근 연도를 T로 사용."""
    by_year = imports_long.groupby("period")["value"].sum()
    total = by_year.max()
    ok = by_year[by_year >= total * coverage]
    return int(ok.index.max())
```

T 시점 데이터가 없는 국가는 후보에서 제외하고 `excluded_reasons`에 남긴다.

### 6.3 단계별 DataFrame 스키마와 코드

**`df_market`** (Stage 1 산출물, index = `iso3`)

| 컬럼 | 설명 |
|---|---|
| `iso3`, `iso2`, `name_ko`, `name_en` | 국가 식별 (`country_codes.csv`와 조인) |
| `imp_{T-3}`, `imp_{T-1}`, `imp_{T}` | 총수입액 (USD) |
| `kor_{T-3}`, `kor_{T-1}`, `kor_{T}` | 한국산 수입액 (USD) |
| `market_size` | `imp_T` |
| `cagr3_pct`, `yoy_pct` | 성장률 |
| `korea_share_pct` | 한국 점유율 |
| `export_gap_pp` | `korea_world_share_pct − korea_share_pct` |

```python
# blueocean/pipeline/funnel.py
import numpy as np
import pandas as pd
from ..services import comtrade
from .scoring import score

HARD_CUT_USD = 10_000_000   # 1,000만 달러
LITE_KEYS = ["market_size", "growth_3y", "growth_1y", "korea_share"]  # Comtrade 1회 수집으로 계산 가능한 항목


def _pivot(df: pd.DataFrame, prefix: str, years: list[int]) -> pd.DataFrame:
    p = df.pivot_table(index="reporter_iso3", columns="period", values="value", aggfunc="sum")
    return p.reindex(columns=years).rename(columns=lambda y: f"{prefix}_{y}")


def stage1_market_frame(hs6: str, T: int, countries: pd.DataFrame) -> pd.DataFrame:
    years = [T - 3, T - 1, T]
    world = comtrade.imports(hs6, reporter="all", partner=0,   years=years)   # ① 각국 총수입
    kor   = comtrade.imports(hs6, reporter="all", partner=410, years=years)   # ② 한국산 수입

    m = _pivot(world, "imp", years).join(_pivot(kor, "kor", years), how="left")
    m[[f"kor_{y}" for y in years]] = m[[f"kor_{y}" for y in years]].fillna(0)  # 행이 없으면 한국산 수입 0으로 간주

    m = m[m.index.isin(countries.index)].drop(index="KOR", errors="ignore")    # 실제 국가만, 한국 제외
    m = m.join(countries[["iso2", "name_ko", "name_en", "currency_code"]])

    m["market_size"]     = m[f"imp_{T}"]
    m["yoy_pct"]         = (m[f"imp_{T}"] / m[f"imp_{T-1}"] - 1) * 100
    m["cagr3_pct"]       = ((m[f"imp_{T}"] / m[f"imp_{T-3}"]) ** (1 / 3) - 1) * 100
    m["korea_share_pct"] = m[f"kor_{T}"] / m[f"imp_{T}"] * 100

    kor_exp   = comtrade.exports(hs6, reporter=410,   partner=0, years=[T])["value"].sum()   # ③
    world_exp = comtrade.exports(hs6, reporter="all", partner=0, years=[T])["value"].sum()
    m.attrs["korea_world_share_pct"] = kor_exp / world_exp * 100
    m["export_gap_pp"] = m.attrs["korea_world_share_pct"] - m["korea_share_pct"]

    return m.replace([np.inf, -np.inf], np.nan)


def stage1_filter(m: pd.DataFrame) -> pd.DataFrame:
    # 하드컷(1,000만 달러) + 1차 사냥 필터(Export Gap > 0). 예전 Utility 바 체크박스가 하던 일을 여기서 고정 적용
    return m[(m["market_size"] >= HARD_CUT_USD) & (m["export_gap_pp"] > 0)].copy()


def stage2_lite(m: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    lite = score(m, keys=LITE_KEYS)
    return lite.sort_values("score", ascending=False).head(top_n)


def stage3_full(cand: pd.DataFrame, hs6: str, T: int) -> pd.DataFrame:
    from ..services import competitors, trends, fx, tariff
    cand = cand.copy()
    cand = cand.join(competitors.top3_share(hs6, cand.index, T))       # top3_share_pct, top3 상세(리스트)  ← Comtrade ④
    cand["trend_momentum"]   = trends.momentum(hs6, cand["iso2"])       # ← SerpAPI
    cand = cand.join(fx.change_3y_krw(cand["currency_code"]))           # fx_change_3y_pct + C-5용 값 ← 수출입은행(주) + yfinance(보조) (§5.3)
    cand = cand.join(tariff.fetch_barriers(hs6, cand))                  # tariff_rate_pct, ntb_items ← KITA 트레이드내비 크롤링 (§5.4)
    return score(cand)  # 8개 항목 100점


def run(hs6: str) -> pd.DataFrame:
    countries = load_countries()                 # data/country_codes.csv → index=iso3
    T = pick_base_year(comtrade.imports(hs6, reporter="all", partner=0, years=None))
    m = stage1_filter(stage1_market_frame(hs6, T, countries))
    cand = stage2_lite(m, top_n=50)
    full = stage3_full(cand, hs6, T)
    return full.sort_values("score", ascending=False).head(20).assign(rank=lambda d: range(1, len(d) + 1))
```

> `competitors.top3_share()` 내부: `reporter=<iso>, partner=all, flow=M` 호출 → 집계 파트너·`World`(0)·`KOR` 제외 → 금액 상위 3개 → `sum / imp_T × 100` = `top3_share_pct`, 이름·개별 점유율은 `top3` 컬럼(list of dict)에 보관 (경쟁국 팝오버용).

### 6.4 캐시 전략

| 대상 | 키 | 저장 | TTL |
|---|---|---|---|
| Comtrade 응답 | `(flow, reporter, partner, hs6, year)` | Parquet (`data/cache/comtrade/`) | 7일 (연간 데이터라 거의 안 변함) |
| SerpAPI 트렌드 | `(hs6, iso2)` | JSON | 7일 |
| 환율 (한국수출입은행 / yfinance) | `(YYYYMMDD)` / `(통화 목록, 날짜)` | 메모리 `ttl_cache` + JSON (`data/cache/fx/`) | 24시간. 수출입은행의 3년 전 날짜 응답은 영구 (**빈 응답·실패는 캐시하지 않음**) |
| 관세율·비관세장벽 (트레이드내비) | `(hs6, 국가코드)` | 메모리 `ttl_cache` + JSON (`data/cache/tariff/`) | 7일 (**실패 응답은 캐시하지 않음**) |
| 최종 분석 결과 | `(hs6)` | JSON | 24시간 |

### 6.5 예외 처리 규칙

| 상황 | 처리 |
|---|---|
| 해당 HS6 데이터 없음 | 빈 결과 + `error.code = "NO_DATA"` → UI에 "해당 품목 데이터가 없습니다" |
| 후보가 20개 미만 | 있는 만큼만 반환, `meta.count`에 개수 |
| SerpAPI/환율 소스 실패 | 해당 항목만 중립값 0.5 + `data_flags`. 전체 분석은 계속 진행 |
| Comtrade 한도 초과(429) | 다음 키로 전환해 재시도 → 전 키 소진 시 지수 백오프 후 캐시된 최근 결과 반환 + `meta.stale = true` |
| 트레이드내비 차단(403/429)·응답 구조 변경·타임아웃 | 백오프 재시도 3회 후 해당 국가만 결측(중립 0.5 + `tariff_missing`), 실패는 캐시하지 않음. 응답 파싱이 전부 실패하면 운영자 알림 로그(구조 변경 의심) |
| 한국수출입은행 미고시 통화 | **예외 없이** yfinance로 보조 조회 (`fx_fallback_yfinance` 플래그). 분석 계속 |
| 한국수출입은행 휴일 빈 응답 | 직전 영업일로 최대 7일 거슬러 조회 |
| 한국수출입은행 호출 자체 실패(네트워크·인증·JSON 오류) | `try / except`로 흡수, 전 통화를 yfinance로 보조 조회 |
| yfinance 실패(429·차단·티커 없음·형식 변경) | `except Exception`으로 흡수하고 로그만 남김. 해당 통화만 결측(중립 0.5 + `fx_missing`), C-5는 안내 문구. 분석 전체는 계속 진행 |
| 분석 시간이 김(첫 조회) | `POST /api/analyze` → `job_id` 즉시 반환, 프론트가 `GET /api/jobs/<id>` 폴링 (스켈레톤 UI 표시) |

---

## 7. Flask 애플리케이션 구조

### 7.1 디렉터리

```
blue_ocean_finder/
├─ app.py                         # create_app() 호출, 실행 진입점
├─ config.py                      # 환경변수, 캐시 경로, TTL
├─ requirements.txt               # flask, pandas, numpy, requests, pyarrow, python-dotenv, yfinance (버전 고정)
├─ .env.example
├─ blueocean/
│  ├─ __init__.py                 # create_app()
│  ├─ routes/
│  │  ├─ pages.py                 # GET /  (Jinja 렌더)
│  │  └─ api.py                   # /api/* JSON 엔드포인트
│  ├─ services/                   # 외부 API 클라이언트 (DataFrame 반환)
│  │  ├─ comtrade.py
│  │  ├─ competitors.py           # Comtrade ④ Top3 처리
│  │  ├─ trends.py                # SerpAPI
│  │  ├─ fx.py                    # 환율: 한국수출입은행(주) + yfinance(보조 Fallback)
│  │  ├─ tariff.py                # KITA 트레이드내비 크롤러 (관세율·비관세장벽)
│  │  └─ cache.py                 # ttl_cache (Streamlit @st.cache_data 대응)
│  ├─ pipeline/
│  │  ├─ funnel.py                # §6.3
│  │  ├─ scoring.py               # §4.4 (SCORE_SPEC)
│  │  └─ insight.py               # AI Insight 문장 생성
│  ├─ templates/
│  │  ├─ base.html
│  │  ├─ index.html               # 아래 partial을 include
│  │  └─ components/
│  │     ├─ _header.html   _hero.html   _ai_insight.html   _dashboard.html
│  │     ├─ _trade_barriers.html   _fx_rate.html   _blue_ocean_map.html
│  │     └─ _export_gap_trend.html   _ranking_table.html
│  └─ static/
│     ├─ css/app.css                                 # --hero-box-h 등 변수
│     └─ js/  state.js  globe.js  charts.js  ranking_table.js  popover.js
├─ data/
│  ├─ country_codes.csv           # iso3, iso2, comtrade_code, tradenavi_code, name_ko, name_en, currency_code, lat, lon
│  ├─ hs_keyword_map.csv          # hs6, keyword_en, keyword_local
│  └─ cache/
└─ tests/  test_scoring.py  test_funnel.py  test_api.py
```

### 7.2 라우트

| Method | Path | 설명 | 사용 컴포넌트 |
|---|---|---|---|
| GET | `/` | 페이지 셸 렌더 | 전체 |
| GET | `/api/hs/suggest?q=` | HS코드/품목명 자동완성 | Header |
| GET | `/api/analyze?hs=` | 깔때기 실행 결과(Top 20 + 메타). 캐시 미스가 오래 걸리면 `202 + job_id` | A, B, C-2, C-3 |
| GET | `/api/jobs/<job_id>` | 비동기 작업 상태/결과 | 로딩 |
| GET | `/api/country/<iso3>/detail?hs=` | 선택 국가 상세: `gap_trend`, `insight` | B, C-4 |
| GET | `/api/fx/latest` | USD→KRW 오늘 고시환율 (한국수출입은행, 실패 시 yfinance) | Header 토글 |
| GET | `/api/export.csv?hs=` | Top 20 CSV | Header |
| GET | `/api/export.html?hs=` | 정적 HTML 스냅샷 | Header |
| GET | `/api/score-spec` | `SCORE_SPEC` JSON (배점표·수식 모달용) | Header 모달 |

```python
# blueocean/routes/api.py (요약)
from flask import Blueprint, jsonify, request
from ..pipeline import funnel

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.get("/analyze")
def analyze():
    hs6 = normalize_hs(request.args.get("hs", ""))          # 숫자만, 앞 6자리
    if not hs6:
        return jsonify(error={"code": "BAD_HS", "message": "HS코드를 6자리 숫자로 입력하세요."}), 400
    df = cache.get_or_compute(f"analyze:{hs6}", lambda: funnel.run(hs6), ttl=24 * 3600)
    return jsonify(to_analyze_response(hs6, df))            # §7.3 스키마로 직렬화 (NaN → null)
```

### 7.3 `/api/analyze` 응답 스키마

```json
{
  "meta": {
    "hs6": "854140",
    "hs_desc": "Solar Cells & Modules",
    "base_year": 2024,
    "korea_world_share_pct": 16.6,
    "count": 20,
    "funnel": { "stage1": 141, "stage2": 50, "stage3": 20 },
    "stale": false,
    "generated_at": "2026-09-20T09:00:00+09:00"
  },
  "top20": [
    {
      "rank": 1,
      "iso3": "MEX", "iso2": "MX", "name_ko": "멕시코", "name_en": "Mexico",
      "lat": 23.6, "lon": -102.5,
      "score": 87.0,
      "potential": 88.5,
      "market_size_usd": 1840000000,
      "korea_share_pct": 1.2,
      "export_gap_pp": 15.4,
      "growth": {
        "direction": "up",
        "yoy_pct": 12.3,
        "cagr3_pct": 9.8,
        "prev_year": 2023, "prev_value_usd": 1640000000,
        "curr_year": 2024, "curr_value_usd": 1840000000
      },
      "competitors": {
        "top3_share_pct": 58.3,
        "top3": [
          { "iso3": "USA", "name_ko": "미국", "name_en": "United States", "share_pct": 32.1 },
          { "iso3": "CHN", "name_ko": "중국", "name_en": "China",         "share_pct": 15.4 },
          { "iso3": "DEU", "name_ko": "독일", "name_en": "Germany",       "share_pct": 10.8 }
        ]
      },
      "barriers": {
        "tariff_rate_pct": 0.0,
        "tariff_type": "FTA",
        "ntb_count": 2,
        "ntb_items": ["수입 인증 요건", "…"],
        "fetched_at": "2026-09-20T09:00:00+09:00"
      },
      "fx": {
        "currency": "MXN",
        "source": "yfinance",
        "change_3y_pct": -5.9,
        "krw_per_local_now": 73.4, "krw_per_local_then": 78.0,
        "now_date": "2026-09-18", "then_date": "2023-09-20"
      },
      "score_breakdown": { "market_size": 13.1, "growth_3y": 12.4, "growth_1y": 8.0, "trend": 3.2, "fx_3y": 1.8,
                           "korea_share": 24.1, "top3_share": 7.9, "tariff": 9.5 },
      "data_flags": ["fx_fallback_yfinance"]
    }
  ],
  "world_market_size_usd": 25910000000
}
```

- `growth.direction`: `"up" | "down" | "flat" | null` — 프론트는 이 값으로 ⬆️/⬇️/`–`를 결정한다.
- `competitors.top3[]`는 **점유율 내림차순**, 한국 제외.
- `fx`: `source`는 `"KEXIM"`(수출입은행 고시 통화, 예: `EUR`, `JPY`) 또는 `"yfinance"`(미고시 통화 보조 조회, 예시의 MXN)다. 보조 소스를 쓴 국가는 `data_flags`에 `fx_fallback_yfinance`(정보용)가 붙는다. **두 소스 모두 실패**하면 `source: null`, 값은 `null`, `data_flags: ["fx_missing"]`이며 환율 점수는 중립 2.5/5다. C-5 카드는 이 값으로 그린다.
- `barriers`: C-1 카드가 이 값으로 그린다. 크롤링 실패 시 `tariff_rate_pct: null` + `data_flags: ["tariff_missing"]`.
- `score_breakdown`은 항목별 획득 점수 (`평가기준` 모달의 "이 나라 점수 근거"에 사용).

**`/api/country/<iso3>/detail` (요약)**

```json
{
  "gap_trend": [ { "year": 2015, "total_import_usd": 0, "korea_export_usd": 0, "export_gap_pp": 0.0 } ],
  "insight": { "headline": "…", "body": "…", "chips": [], "action": "…" }
}
```

---

## 8. 개발 순서 (권장)

| 단계 | 산출물 | 완료 기준 |
|---|---|---|
| M1 | `services/comtrade.py` + `country_codes.csv` | HS6 하나로 `df_market` 생성, 멕시코의 한국 점유율·성장률이 Comtrade 웹 조회값과 일치 |
| M2 | `pipeline/scoring.py` + `tests/test_scoring.py` | 가중치 합 100 assert, 결측/방향 반전/분산 0 케이스, **성장률 규칙(−값→0, 15%→0.5, 30%↑→1) 테스트 통과** |
| M3 | `pipeline/funnel.py` Stage 1~2 | **1,000만 달러 하드컷**·Gap 필터·상위 50 추출 |
| M4 | Flask 골격 + `/api/analyze` (Stage 3는 관세·트렌드·환율 stub=중립값) | 표/지구본이 실데이터로 그려짐 |
| M5 | UI: 레이아웃(사이드바·Utility 삭제 반영), AI Insight 배치, Top 20 팝오버 2종 | §3.9 인터랙션 수용 기준 통과 |
| M6 | `services/fx.py`(한국수출입은행 + **yfinance Fallback**), `services/trends.py`(SerpAPI) 연동 | **전 통화의 수출입은행 고시 여부 / Yahoo 티커 존재 여부 점검**, 미고시 통화가 에러 없이 yfinance로 채워짐, 국가 클릭 시 3년 전 vs 현재 그래프 |
| M7-a | **트레이드내비 XHR 값을 `config.py`에 수동 입력** (팀 담당, 추후) — 입력 전에는 크롤러가 `ok=False`를 반환해 관세 점수는 중립 | 값 입력 후 대표 국가 1건 조회 성공 |
| M7-b | `services/tariff.py` 크롤러 + `ttl_cache` 연동 | 점수 8개 항목 전부 실데이터, **같은 (HS, 국가) 재조회 시 외부 요청 0건** |
| M8-a | AI Insight 콘텐츠·프롬프트 (파이프라인 완성 후) | 임시 stub을 실제 생성 로직으로 교체 |
| M8 | 캐시·에러 처리·CSV/HTML 내보내기·QA | §6.5 예외 시나리오 통과 |

**UI 수용 기준(체크리스트)**

- [ ] 좌측 5개 아이콘 사이드바가 화면 어디에도 없다.
- [ ] 화면 하단 Utility 바가 없고, 품목은 헤더 검색창, 시장은 지구본/표 클릭으로만 바뀐다.
- [ ] AI Insight가 Hero 바로 아래 중앙에 있고, 폭·높이가 지구본 박스와 비슷하다(창 크기를 바꿔도 유지).
- [ ] 표 컬럼명이 `Growth 추세`, `한국 점유율`, `경쟁국`이며 `Potential`/`Penetration`/`Top3` 문구가 없다.
- [ ] `Growth 추세`는 ⬆️/⬇️만 보이고, 클릭하면 전년대비 수입성장률 수치가 뜨며 바깥 클릭/Esc로 닫힌다.
- [ ] `경쟁국`은 점유율 수치만 보이고, 클릭하면 Top 3 국가 이름이 뜬다.
- [ ] 두 클릭 인터랙션이 행 선택(타깃 락온)을 동시에 발동시키지 않는다.
- [ ] 표에서 국가 행을 클릭하면 Real-time Exchange Rate 카드가 해당국 통화 ↔ KRW **3년 전 vs 현재** 그래프로 바뀐다 (추가 API 호출 없음).
- [ ] 수출입은행 미고시 통화 국가(예: 멕시코)도 에러 없이 yfinance로 환율 점수가 채워지고 출처 배지가 `yfinance`로 표시된다. yfinance까지 실패하면 그 국가만 중립 처리되고 분석은 계속된다.
- [ ] Trade Show Schedule가 화면에 없고, 좌측 컬럼의 AI Insight 아래·환율 카드 위에 Trade Barriers 카드가 있다.
- [ ] 시장규모 1,000만 달러 미만 국가가 결과에 없다.
- [ ] HS Code 검색 시 백엔드가 트레이드내비를 호출해 `tariff_rate_pct`를 채우고, 같은 (HS, 국가)를 다시 조회하면 캐시에서 반환된다.
- [ ] 트레이드내비 호출이 실패한 국가도 분석은 계속되며 `tariff_missing` 플래그가 남는다.
- [ ] 역성장 국가의 성장률 항목 점수가 0이다 (`score_breakdown.growth_3y`, `growth_1y`).
- [ ] 표의 ⬆️/⬇️ 방향과 성장률 팝오버의 부호, 점수 항목 '1년 성장률'의 입력값이 같은 `yoy_pct`이다.

---

## 9. 초안 이미지에서 발견된 유의점 (목업 → 실데이터 전환 시)

1. **초안 표의 `KR Korea` 행**: 한국은 출발국이므로 타깃 목록에서 **제외**해야 한다(§6.3 `drop(index="KOR")`).
2. **초안 수치의 모순**: 베트남 한국 점유율 73.0%인데 Score 85 등 — 점수식상 한국 점유율이 높으면(25점 항목) 점수가 낮아야 한다. 초안 수치는 **더미 데이터**이므로 실데이터로 교체 시 순위가 크게 달라진다.
3. **초안 그래프 연도(2012~2020)** 는 더미. 실제로는 T 기준 최근 10년.
4. **버블 차트 설명 문구**: 초안은 "우상단(Q1)"이라 적혀 있으나 블루오션은 **좌상단**(낮은 점유율·높은 잠재력)이다. 문구/라벨을 수정한다.
5. **환율 카드의 `USD/VND`** 는 멕시코 선택 상태에서 맞지 않는 값이다. §3.6처럼 선택 국가 통화에 연동한다.

---

## 10. 확정 사항과 남은 이슈

### 10.1 확정 사항 (v2.4까지 반영 완료)

| # | 항목 | 확정 내용 | 반영 위치 |
|---|---|---|---|
| 1 | `경쟁국` 컬럼 표시 | 기본 = 한국 제외 Top 3 점유율 **합계**. 클릭하면 **3개 국가의 이름과 국가별 점유율** 표시 | §3.9.2 |
| 2 | 경쟁국 Top 3에 한국 포함 여부 | **한국 제외** (한국 점유율 25점과 이중 반영 방지) | §3.9.2, §4.2 |
| 3 | 성장률 점수 | 역성장 0점 / +30% 이상 만점 / 사이 선형. **절대평가로 확정** — 임계값을 실데이터에 맞춰 조정하지 않음 (3년 CAGR·1년 YoY 모두) | §4.2, §4.4 |
| 4 | 시장규모 하드컷 | **1,000만 달러** 미만 국가 제외 | §3.9, §6.1, §6.3 |
| 5 | 환율 소스 (주) | **한국수출입은행 오픈 API.** 3년치 시계열 불필요 — **오늘 vs 정확히 3년 전 같은 날짜, 두 시점만** 비교 | §5.3 |
| 6 | 환율 소스 (Fallback) | 수출입은행 미고시 통화(MXN, VND, PLN 등)는 **`try / except`로 에러 없이 yfinance 보조 조회.** 두 소스 모두 실패한 통화만 결측(중립 0.5) | §5.3.3, §5.3.4 |
| 7 | C-5 환율 카드 | 국가 클릭 시 해당국 통화 ↔ KRW **3년 전 vs 현재** 비교 그래프로 교체. 출처(KEXIM / yfinance) 배지 표시 | §3.6, §3.10 |
| 8 | Comtrade 호출 한도 | 여러 계정 키를 **키 풀**로 돌려 사용 | §5.1 |
| 9 | Trade Show Schedule | **컴포넌트 삭제** (KOTRA 박람회 연동 제거). 그 자리(AI Insight 아래·좌측·환율 카드 위)에 Trade Barriers 카드 배치 | §3.5 |
| 10 | AI Insight | 위치·크기 레이아웃만 먼저 구현. **콘텐츠·프롬프트는 데이터 파이프라인 완성 후** 진행 | §3.4 |
| 11 | 관세율·비관세 장벽 | **KITA 트레이드내비 XHR 직접 호출.** `requests`로 실시간, Payload에 HS·국가코드 동적 삽입, 헤더 위장, TTL 캐시 | §5.4 |
| 12 | 트레이드내비 실측값 | URL·메서드·Payload 필드명·국가코드·응답 포맷은 **팀이 `config.py`에 추후 수동 입력.** 입력 전에는 stub이 실패로 처리해 관세 점수는 중립 | §5.4.2 |
| 13 | 비관세 장벽 | 점수에는 넣지 않고 **C-1 카드에 표시만** | §3.5, §5.4.1 |

### 10.2 남은 이슈

| # | 이슈 | 제안 |
|---|---|---|
| 1 | **크롤링 차단·약관** — 헤더 위장은 차단 가능성을 낮출 뿐 보장하지 않음. 이용약관·`robots.txt`, 외부 공개 시 허용 범위 미확인 | 캐시(7일)로 호출 수 최소화, 지연·동시성 제한, 실패 시 중립 처리. 운영 전 약관 확인 |
| 2 | **yfinance Fallback 안정성** — 비공식 라이브러리, 일부 통화 티커 부재, 과호출 시 차단 가능. 미고시 통화 국가(예: 멕시코)의 환율 점수가 이 소스에 의존 | 버전 고정 + 배치 조회 + 24시간 캐시 + `try / except`로 결측 시 중립 처리(§5.3.3). M6 시작 전 전 통화의 수출입은행 고시 여부·Yahoo 티커 존재 여부 점검 스크립트 실행 |
| 3 | **수출입은행 인증키·호출 한도·고시 시각** | 키 발급 후 일일 한도 확인. 분석당 2~10회 호출 + 캐시라 부담은 작음. 영업일 오전 11시경 고시라 오전에는 직전 영업일 값이 쓰임 |
