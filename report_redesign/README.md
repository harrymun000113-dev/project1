# 리포트 신규 디자인 (인디고/네이비) — 병합용

`blueocean/reports.py`(현재 앱에 실제로 연동되어 있는 Word 리포트 생성기, 네이비/블루 팔레트)를
대체할 새 디자인 시안. Node.js `docx` 패키지로 만든 예시이며, 값은 전부 하드코딩된 더미
데이터("예시국 A", 82점 등)라 실행하면 항상 같은 샘플이 나온다.

## 실행 방법

```
npm install
node build_report.js
```

`blue_ocean_report_sample.docx`가 생성된다. (이미 한 번 생성해서 폴더에 포함해뒀다.)

## 병합할 때 참고할 것 — 실제 데이터 스키마

`blueocean/reports.py`의 `generate_blue_ocean_report(data, ...)`가 받는 `data` 딕셔너리
허용 키는 다음과 같다 (그 파일 상단 docstring 참고):

```
country, blue_ocean_score, market_opportunity_score, penetration_opportunity_score,
growth_1y, cagr_3y, korea_market_share, global_korea_share, export_gap,
tariff_rate, top3_concentration, item_name, hs_code, project_name, date
```

`rank`(종합 순위)는 스키마에 없는 선택 필드 — 호출 측이 넘기지 않으면 항상 "확인되지 않음"으로
남겨야 한다 (지어내지 않기 위한 규칙).

`reports.py`는 값이 없으면 절대 추측하지 않고 "확인되지 않음"으로 표시하는 원칙과, OpenAI 키가
있으면 AI로 서술 문장을 생성하고 없으면 규칙 기반 고정 문장으로 폴백하는 로직을 이미 갖고 있다.
이 새 디자인을 병합할 때 그 두 가지 원칙(값 없으면 추측 금지 / AI 실패 시 자동 폴백)은 그대로
유지해야 한다.

`build_report.js`의 각 섹션(요약 KPI, 선정 이유, 리스크, 진출 선례, 액션 체크리스트, 접촉 채널,
종합 결론, 산출 근거)에 박혀 있는 예시 문자열을 위 스키마의 실제 값으로 교체하면 된다. Python
쪽으로 이식할지, Node 스크립트를 그대로 두고 Python이 JSON을 넘겨 실행할지는 병합하는 쪽에서
정하면 된다.

## 폴더 구성

- `build_report.js` — 리포트 생성 스크립트 (더미 데이터 하드코딩)
- `cover_bg.png`, `chart_growth.png` — 표지/그래프 이미지 자산
- `blue_ocean_report_sample.docx` — 실행 결과 샘플 (미리보기용)
- `package.json` — `docx` 의존성
