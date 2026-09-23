const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, AlignmentType, Header, Footer, PageNumber,
  LevelFormat, VerticalAlign, PageBreak, ImageRun,
  HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom, TextWrappingType, TextWrappingSide,
} = require("docx");
const fs = require("fs");

// ---- 색상 팔레트 (신규 디자인: 인디고/네이비 계열) ----
const INDIGO = "4A57B0";       // 표지 배경
const INDIGO_DEEP = "232C63";  // 섹션 배지, 표 헤더, 타이틀
const INDIGO_MID = "3C4998";
const NAVY_TEXT = "1E2550";
const LAVENDER_LIGHT = "EEF0FA"; // 요약 콜아웃 박스
const GREEN = "2E7D4F";
const GREEN_LIGHT = "E8F3EC";
const AMBER = "9A6B12";
const AMBER_LIGHT = "FBF1DA";
const AMBER_BORDER = "D9A441";
const RED = "B23A3A";
const RED_LIGHT = "FBEAEA";
const GRAY_TEXT = "5B6472";
const GRAY_SOFT = "8A93A3";
const BORDER_GRAY = "DCE1E8";
const ROW_ALT = "F6F7FB";
const BOX_GRAY = "F4F5F8";

const FONT = "Malgun Gothic";

function noBorders() {
  const n = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return { top: n, bottom: n, left: n, right: n };
}
function thinBorders(color = BORDER_GRAY) {
  const b = { style: BorderStyle.SINGLE, size: 4, color };
  return { top: b, bottom: b, left: b, right: b };
}
function sideBorder(color, size = 30) {
  const n = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return { top: n, bottom: n, right: n, left: { style: BorderStyle.SINGLE, size, color } };
}

// =====================================================================
// 섹션 헤더 — 남색 사각 배지(번호) + 타이틀 + 옅은 회색 설명 + 언더라인
// =====================================================================
let sectionCounter = 0;
function sectionHeader(title, note, opts = {}) {
  sectionCounter += 1;
  const num = opts.num || String(sectionCounter);
  return new Table({
    width: { size: 9500, type: WidthType.DXA },
    columnWidths: [520, 8980],
    borders: noBorders(),
    rows: [new TableRow({
      children: [
        new TableCell({
          width: { size: 520, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: INDIGO_DEEP },
          verticalAlign: VerticalAlign.CENTER,
          borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 6, color: INDIGO_DEEP } },
          margins: { top: 50, bottom: 50, left: 0, right: 0 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
            new TextRun({ text: num, bold: true, color: "FFFFFF", size: 22, font: FONT }),
          ]})],
        }),
        new TableCell({
          width: { size: 8980, type: WidthType.DXA },
          verticalAlign: VerticalAlign.CENTER,
          borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 6, color: INDIGO_DEEP } },
          margins: { top: 50, bottom: 50, left: 160, right: 0 },
          children: [new Paragraph({ children: [
            new TextRun({ text: title, bold: true, color: NAVY_TEXT, size: 25, font: FONT }),
            ...(note ? [new TextRun({ text: `   ${note}`, italics: true, size: 16, color: GRAY_SOFT, font: FONT })] : []),
          ]})],
        }),
      ],
    })],
  });
}
function sectionSpacer(before = 260, after = 140) {
  return new Paragraph({ spacing: { before, after } });
}
function captionLine(text) {
  return new Paragraph({
    spacing: { before: 70, after: 0 },
    children: [
      new TextRun({ text: "출처: ", bold: true, italics: true, size: 17, color: GRAY_TEXT, font: FONT }),
      new TextRun({ text, italics: true, size: 17, color: GRAY_SOFT, font: FONT }),
    ],
  });
}
function body(text, opts = {}) {
  return new Paragraph({
    alignment: opts.noJustify ? AlignmentType.LEFT : AlignmentType.JUSTIFIED,
    spacing: { after: 120, line: 300 },
    children: [new TextRun({ text, size: 21, color: opts.color || "2A2E36", font: FONT, bold: !!opts.bold, italics: !!opts.italics })],
  });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 90, line: 290 },
    children: [new TextRun({ text, size: 21, font: FONT, color: "2A2E36" })],
  });
}
function noteArrow(text) {
  return new Table({
    width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 9500, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, color: "auto", fill: BOX_GRAY },
      borders: thinBorders(BORDER_GRAY),
      margins: { top: 130, bottom: 130, left: 200, right: 200 },
      children: [new Paragraph({ children: [
        new TextRun({ text: "▼ ", bold: true, color: INDIGO_DEEP, size: 19, font: FONT }),
        new TextRun({ text, bold: true, size: 19, color: NAVY_TEXT, font: FONT }),
      ]})],
    })]})],
  });
}
function grayBox(text) {
  return new Table({
    width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 9500, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, color: "auto", fill: BOX_GRAY },
      borders: thinBorders(BORDER_GRAY),
      margins: { top: 150, bottom: 150, left: 220, right: 220 },
      children: [new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 300 }, children: [
        new TextRun({ text, size: 20, color: "3A3F4B", font: FONT }),
      ]})],
    })]})],
  });
}
function labelCell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: opts.fill || LAVENDER_LIGHT },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 110, bottom: 110, left: 160, right: 140 },
    borders: thinBorders(),
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 20, color: INDIGO_DEEP, font: FONT })] })],
  });
}
function valueCell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: opts.fill ? { type: ShadingType.CLEAR, color: "auto", fill: opts.fill } : undefined,
    margins: { top: 110, bottom: 110, left: 160, right: 140 },
    borders: thinBorders(),
    children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: FONT, bold: !!opts.bold, color: opts.color || "2A2E36" })] })],
  });
}
function navyHeaderCell(text, width) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: INDIGO_DEEP },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 110, bottom: 110, left: 160, right: 140 },
    borders: thinBorders(INDIGO_DEEP),
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 19, color: "FFFFFF", font: FONT })] })],
  });
}

// =====================================================================
// 표지 — 배경은 풀블리드 그라디언트 이미지(고정), 글자는 워드에서 직접 수정 가능한 일반 텍스트
// =====================================================================
const PAGE_W = 11906;
const PAGE_H = 16838;
// ImageRun transformation 단위는 px(96dpi 기준)이므로 twips -> px 변환
const coverBgFloat = new ImageRun({
  type: "png",
  data: fs.readFileSync("cover_bg.png"),
  transformation: { width: Math.round(PAGE_W / 1440 * 96), height: Math.round(PAGE_H / 1440 * 96) },
  floating: {
    horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: 0 },
    verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: 0 },
    wrap: { type: TextWrappingType.NONE, side: TextWrappingSide.BOTH },
    behindDocument: true,
    allowOverlap: true,
    layoutInCell: false,
  },
});

const coverTextChildren = [
  // 첫 문단에 배경 이미지를 함께 앵커링 (문단 자체 높이엔 거의 영향 없음)
  new Paragraph({
    spacing: { before: 200, after: 0 },
    children: [coverBgFloat, new TextRun({ text: "유망시장 발굴 리포트", size: 20, color: "D9DEF5", font: FONT })],
  }),
  new Paragraph({ spacing: { before: 320 }, children: [new TextRun({ text: "BLUE", bold: true, size: 60, color: "FFFFFF", font: FONT })] }),
  new Paragraph({ spacing: { before: 40 }, children: [new TextRun({ text: "OCEAN", bold: true, size: 60, color: "FFFFFF", font: FONT })] }),
  new Paragraph({
    spacing: { before: 40 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "8892D6", space: 10 } },
    children: [new TextRun({ text: "REPORT", bold: true, size: 60, color: "FFFFFF", font: FONT })],
  }),
  new Paragraph({ spacing: { before: 200 }, children: [new TextRun({ text: "무역 통계 데이터 기반 유망 시장 분석 의사결정 브리프", size: 19, color: "C7CDEF", font: FONT })] }),
  new Paragraph({ spacing: { before: 9200 }, children: [new TextRun({ text: "KITA AX 마스터즈", bold: true, size: 20, color: "FFFFFF", font: FONT })] }),
];

// =====================================================================
// 문서 개요 (표지 다음 첫 표)
// =====================================================================
const docInfoTable = new Table({
  width: { size: 9500, type: WidthType.DXA },
  columnWidths: [2400, 7100],
  rows: [
    ["수출 품목", "HS 854140 · 태양광 인버터 부품"],
    ["추천 국가", "예시국 A (Country A)"],
    ["분석 엔진", "Blue Ocean Finder Scoring Model (Ver 1.0)"],
    ["작성 프로젝트", "KITA AX 무역마스터 1차 프로젝트 — Blue Ocean Finder"],
    ["조사 기준일", "2026.09"],
    ["발행 일자", "2026-09-23"],
  ].map(([k, v], i) => new TableRow({
    children: [labelCell(k, 2400, { fill: i % 2 === 0 ? LAVENDER_LIGHT : "FFFFFF" }), valueCell(v, 7100, { bold: true, fill: i % 2 === 0 ? ROW_ALT : "FFFFFF" })],
  })),
});

// =====================================================================
// 1. 요약 — KPI 타일
// =====================================================================
function kpiTile(label, value, opts = {}) {
  return new TableCell({
    width: { size: 2375, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: opts.fill || "FFFFFF" },
    borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 14, color: opts.accent || INDIGO_DEEP } },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 180, bottom: 180, left: 140, right: 140 },
    children: [
      new Paragraph({ children: [new TextRun({ text: label, size: 16, color: GRAY_SOFT, font: FONT, bold: true })] }),
      new Paragraph({ spacing: { before: 70 }, children: [new TextRun({ text: value, bold: true, size: 30, color: opts.valColor || NAVY_TEXT, font: FONT })] }),
    ],
  });
}
const kpiTable = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [2375, 2375, 2375, 2375],
  rows: [new TableRow({ children: [
    kpiTile("BLUE OCEAN SCORE", "82", { valColor: INDIGO_DEEP }),
    kpiTile("한국 점유율", "3.0%", { valColor: AMBER }),
    kpiTile("최근 1년 성장률", "+15%", { valColor: GREEN }),
    kpiTile("종합 순위", "3위 / 48개국", { valColor: NAVY_TEXT }),
  ]})],
});

const summaryCallout = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
  rows: [new TableRow({ children: [new TableCell({
    width: { size: 9500, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: LAVENDER_LIGHT },
    borders: sideBorder(INDIGO_MID),
    margins: { top: 160, bottom: 160, left: 240, right: 240 },
    children: [new Paragraph({ spacing: { line: 320 }, children: [
      new TextRun({ text: "예시국 A", bold: true, color: INDIGO_DEEP, size: 21, font: FONT }),
      new TextRun({ text: " — 최근 3년간 이 시장의 한국산 수입은 ", size: 21, font: FONT }),
      new TextRun({ text: "15% 증가", bold: true, color: GREEN, size: 21, font: FONT }),
      new TextRun({ text: "했지만, 한국의 시장 점유율은 아직 ", size: 21, font: FONT }),
      new TextRun({ text: "3%대로 낮은 수준", bold: true, color: AMBER, size: 21, font: FONT }),
      new TextRun({ text: "입니다. 성장 속도에 비해 한국 기업의 진입이 아직 충분히 이뤄지지 않은 시장입니다.", size: 21, font: FONT }),
    ]})],
  })]})],
});

// =====================================================================
// 2. 선정 이유 + 선택 그래프
// =====================================================================
const whyReasonBullets = [
  bullet("한국산 제품 수입 증가율이 최근 1년 기준 15%로, 전체 조사 대상국 평균(6%)보다 뚜렷하게 높습니다."),
  bullet("반면 한국의 이 시장 점유율은 3%에 그쳐, 한국의 세계 평균 점유율(9%) 대비 낮은 편입니다 — 이 격차가 클수록 \"아직 개척되지 않은 여지\"가 크다는 뜻입니다."),
  bullet("상위 3개 경쟁국이 시장의 58%를 차지하고 있어 경쟁이 아주 치열한 수준은 아닙니다."),
];
const growthChartImage = new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 160, after: 0 },
  children: [new ImageRun({ type: "png", data: fs.readFileSync("chart_growth.png"), transformation: { width: 480, height: 220 } })],
});

// =====================================================================
// 3. 리스크 및 진입장벽
// =====================================================================
function riskRow(name, level, desc, i) {
  const map = { "상": { bg: RED_LIGHT, fg: RED }, "중": { bg: AMBER_LIGHT, fg: AMBER }, "하": { bg: GREEN_LIGHT, fg: GREEN } };
  const c = map[level];
  const rowFill = i % 2 === 0 ? ROW_ALT : "FFFFFF";
  return new TableRow({
    children: [
      valueCell(name, 2200, { bold: true, fill: rowFill, color: INDIGO_DEEP }),
      new TableCell({
        width: { size: 1300, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: c.bg },
        verticalAlign: VerticalAlign.CENTER, borders: thinBorders(),
        margins: { top: 90, bottom: 90, left: 100, right: 100 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: level, bold: true, color: c.fg, size: 21, font: FONT })] })],
      }),
      valueCell(desc, 6000, { fill: rowFill }),
    ],
  });
}
const riskTableFinal = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [2200, 1300, 6000],
  rows: [
    new TableRow({ tableHeader: true, children: [navyHeaderCell("리스크 점검 항목", 2200), navyHeaderCell("심각도", 1300), navyHeaderCell("설명 및 대응 관점", 6000)] }),
    riskRow("관세 부담", "중", "실효관세율 8% — 감당 가능한 수준이나 원가 구조에 반영 필요", 0),
    riskRow("경쟁 강도", "하", "상위 3개국 점유율 58% — 독과점 수준은 아니며 신규 진입 여지 있음", 1),
    riskRow("비관세 규제", "중", "인증·통관 관련 규제 존재 (세부 항목은 별도 확인 필요)", 2),
  ],
});

// =====================================================================
// 4. 한국 기업 진출 선례 (출처 명시)
// =====================================================================
function precedentRow(company, method, year, source, i) {
  const fill = i % 2 === 0 ? ROW_ALT : "FFFFFF";
  return new TableRow({
    children: [
      valueCell(company, 2200, { fill, color: INDIGO_DEEP, bold: true }),
      valueCell(method, 3300, { fill }),
      valueCell(year, 1200, { fill }),
      valueCell(source, 2800, { fill, color: GRAY_TEXT }),
    ],
  });
}
const precedentTable = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [2200, 3300, 1200, 2800],
  rows: [
    new TableRow({ tableHeader: true, children: [navyHeaderCell("기업명", 2200), navyHeaderCell("진출 방식", 3300), navyHeaderCell("연도", 1200), navyHeaderCell("출처", 2800)] }),
    precedentRow("(예시) A전자", "현지 유통사와 총판 계약 체결 후 간접 수출", "2022", "KOTRA 해외시장뉴스 (예시 링크)", 0),
    precedentRow("(예시) B산업", "현지 인증 취득 후 직접 수출로 전환", "2023", "무역협회 수출입동향 보고서 (예시 링크)", 1),
  ],
});

// =====================================================================
// 5. 다음 액션 체크리스트 — 단계 테이블
// =====================================================================
function stepRow(step, title, desc, i) {
  const fill = i % 2 === 0 ? ROW_ALT : "FFFFFF";
  return new TableRow({
    children: [
      new TableCell({
        width: { size: 1300, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: "auto", fill },
        verticalAlign: VerticalAlign.CENTER, borders: thinBorders(),
        margins: { top: 120, bottom: 120, left: 120, right: 120 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: `${step}`, bold: true, size: 26, color: INDIGO_DEEP, font: FONT }),
          new TextRun({ text: "단계", size: 16, color: GRAY_SOFT, font: FONT }),
        ]})],
      }),
      valueCell(title, 2700, { fill, bold: true }),
      valueCell(desc, 5500, { fill }),
    ],
  });
}
const actionTable = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [1300, 2700, 5500],
  rows: [
    stepRow(1, "관세율·경쟁국 구도 재확인", "본 리포트 수치는 최신 데이터 기준으로 팀 내 재검증 (실효관세율 및 상위 경쟁국 점유율 교차 확인)", 0),
    stepRow(2, "현지 유통·규제 요건 조사", "관련 협회·KOTRA 무역관을 통해 실제 인증/통관 요건 확인 (비관세 장벽 항목 사전 점검)", 1),
    stepRow(3, "소량 샘플 오더 또는 시범 거래 검토", "대량 계약 전 소규모로 시장 반응 테스트 (바이어 반응 및 초기 물류 프로세스 점검)", 2),
  ],
});

// =====================================================================
// 6. 접촉 채널 (참고용)
// =====================================================================
const channelTable = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [2800, 6700],
  rows: [
    new TableRow({ tableHeader: true, children: [navyHeaderCell("접촉 채널", 2800), navyHeaderCell("설명 (참고용)", 6700)] }),
    new TableRow({ children: [valueCell("KOTRA 해당 국가 무역관", 2800, { fill: ROW_ALT, bold: true, color: INDIGO_DEEP }), valueCell("시장 정보 및 바이어 매칭 지원 문의", 6700, { fill: ROW_ALT })] }),
    new TableRow({ children: [valueCell("관련 업종 협회·전시회", 2800, { bold: true, color: INDIGO_DEEP }), valueCell("현지 업계 네트워크 파악", 6700)] }),
    new TableRow({ children: [valueCell("온라인 B2B 플랫폼", 2800, { fill: ROW_ALT, bold: true, color: INDIGO_DEEP }), valueCell("Alibaba 등 해당국 주요 조달 플랫폼을 통한 초기 바이어 탐색", 6700, { fill: ROW_ALT })] }),
  ],
});

// =====================================================================
// 7. 종합 결론 및 방향성
// =====================================================================
const conclusionTable = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
  rows: [new TableRow({ cantSplit: true, children: [new TableCell({
    width: { size: 9500, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: LAVENDER_LIGHT },
    borders: { ...noBorders(), top: { style: BorderStyle.SINGLE, size: 4, color: BORDER_GRAY }, bottom: { style: BorderStyle.SINGLE, size: 4, color: BORDER_GRAY } },
    margins: { top: 0, bottom: 170, left: 0, right: 0 },
    children: [
      new Table({
        width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
        rows: [new TableRow({ children: [new TableCell({
          width: { size: 9500, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: INDIGO_DEEP },
          margins: { top: 110, bottom: 110, left: 240, right: 240 },
          children: [new Paragraph({ children: [new TextRun({ text: "종합 판단:  적극 검토 가능", bold: true, size: 22, color: "FFFFFF", font: FONT })] })],
        })]})],
      }),
      new Paragraph({ spacing: { before: 140, after: 100 }, indent: { left: 240, right: 240 }, children: [
        new TextRun({ text: "(Blue Ocean Score 82 · 리스크 대부분 \"중\" 이하)", italics: true, size: 18, color: GRAY_TEXT, font: FONT }),
      ]}),
      new Paragraph({ spacing: { after: 100, line: 300 }, indent: { left: 240, right: 240 }, children: [new TextRun({
        text: "성장률(+15%)과 낮은 점유율(3%)의 조합은 이 시장이 아직 한국 기업에게 열려 있다는 신호이며, 확인된 리스크(관세 8%, 비관세장벽)는 진입을 막을 정도가 아니라 준비 과정에서 관리 가능한 수준입니다.",
        size: 20, color: "333333", font: FONT,
      })]}),
      new Paragraph({ indent: { left: 240, right: 240 }, children: [
        new TextRun({ text: "권장 방향: ", bold: true, size: 20, color: NAVY_TEXT, font: FONT }),
        new TextRun({ text: "\"다음 액션 체크리스트\"(5번)의 재검증 → 규제 확인 → 소량 샘플 오더 순으로 단계적 접근을 권장합니다. 전면 진입보다는 리스크 확인 후 확대하는 방식이 안전합니다.", size: 20, color: "333333", font: FONT }),
      ]}),
    ],
  })]})],
});
const conclusionNote = new Table({
  width: { size: 9500, type: WidthType.DXA }, columnWidths: [9500], borders: noBorders(),
  rows: [new TableRow({ children: [new TableCell({
    width: { size: 9500, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: AMBER_LIGHT },
    borders: thinBorders(AMBER_BORDER),
    margins: { top: 130, bottom: 130, left: 220, right: 220 },
    children: [new Paragraph({ spacing: { line: 290 }, children: [new TextRun({
      text: "위 판단은 본 리포트에 제시된 데이터(2~3번 항목)만을 근거로 한 요약이며, 최종 진출 결정은 팀 내 추가 검토를 거쳐 확정해야 합니다.",
      bold: true, size: 19, color: AMBER, font: FONT,
    })]})],
  })]})],
});

// =====================================================================
// 문서 (조립)
// =====================================================================
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullet-list", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 260 } } } }] },
    ],
  },
  sections: [{
    // 표지 전용 섹션 — 배경은 풀블리드 이미지(고정), 텍스트는 일반 여백 안에서 편집 가능
    properties: {
      page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: 900, bottom: 900, left: 800, right: 800, header: 0, footer: 0 } },
    },
    children: coverTextChildren,
  }, {
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1100, bottom: 1100, left: 1100, right: 1100 } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: INDIGO_DEEP, space: 6 } },
          tabStops: [{ type: "right", position: 9500 }],
          children: [
            new TextRun({ text: "BLUE OCEAN REPORT", bold: true, size: 16, color: INDIGO_DEEP, font: FONT }),
            new TextRun({ text: "  ·  유망시장 발굴 리포트", size: 14, color: GRAY_SOFT, font: FONT }),
            new TextRun({ text: "\tKITA AX 마스터즈", bold: true, size: 14, color: GRAY_TEXT, font: FONT }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: BORDER_GRAY, space: 6 } },
          tabStops: [{ type: "right", position: 9500 }],
          children: [
            new TextRun({ text: "Blue Ocean Finder Scoring Model", size: 15, color: GRAY_SOFT, font: FONT }),
            new TextRun({ text: "\t- ", size: 15, color: GRAY_SOFT, font: FONT }),
            new TextRun({ children: [PageNumber.CURRENT], size: 15, color: GRAY_SOFT, font: FONT }),
            new TextRun({ text: " -", size: 15, color: GRAY_SOFT, font: FONT }),
          ],
        })],
      }),
    },
    children: [
      new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: "문서 개요", bold: true, size: 21, color: NAVY_TEXT, font: FONT })] }),
      docInfoTable,
      sectionSpacer(320, 0),

      sectionHeader("요약", "※ 핵심 지표 요약 및 한두 문장 결론"),
      sectionSpacer(220, 180),
      kpiTable,
      captionLine("핵심 지표 요약 (예시 데이터) — Blue Ocean Score 산정 기준"),
      sectionSpacer(160, 0),
      summaryCallout,
      sectionSpacer(260, 0),

      sectionHeader("이 시장을 선택한 이유", "※ 데이터 결과 중심의 쉬운 설명 (핵심 근거 3가지)"),
      sectionSpacer(220, 160),
      body("데이터가 말해주는 결과는 다음과 같습니다."),
      ...whyReasonBullets,
      growthChartImage,
      captionLine("예시국 A 한국산 수입액 추이 (예시 데이터) — 실제 반영 시 UN Comtrade 3개년 수치로 대체"),
      sectionSpacer(180, 0),
      noteArrow("산출에 사용된 세부 점수와 계산 방식은 [부록 A]에서 확인할 수 있습니다."),
      sectionSpacer(260, 0),

      sectionHeader("리스크 및 진입장벽", "※ 관세·비관세·경쟁강도 항목별 심각도 표시"),
      sectionSpacer(220, 160),
      body("아래 리스크는 \"진출하지 말라\"는 의미가 아니라, 준비 시 감당해야 할 수준을 미리 가늠하기 위한 정보입니다."),
      riskTableFinal,
      captionLine("리스크 심각도 평가 (예시 데이터) — 관세청 API, UN Comtrade 기준"),
      sectionSpacer(260, 0),

      sectionHeader("한국 기업 진출 선례", "※ 출처 명시 필수"),
      sectionSpacer(220, 160),
      body("웹 검색으로 확인된 유사 업종의 진출 사례입니다. 실제 서비스에서는 최신 검색 결과를 반영해 자동 갱신하며, 확인된 사례가 없는 경우 \"확인된 진출 사례 없음\"으로 명시합니다."),
      precedentTable,
      captionLine("한국 기업 진출 선례 (예시 데이터) — 각 행의 출처는 실제 연동 시 기사·보고서 링크로 대체"),
      sectionSpacer(260, 0),

      sectionHeader("다음 액션 체크리스트", "※ 계산된 값 기준의 일반적 3단계 실행 가이드"),
      sectionSpacer(220, 160),
      body("바로 시작할 수 있는 3단계입니다."),
      actionTable,
      captionLine("실행 로드맵 — 무역 데이터 기반 표준 3단계 검증 프로세스"),
      sectionSpacer(260, 0),

      sectionHeader("접촉 채널 (참고용)", "※ 공개 일반 정보 (참고용 라벨 필수 표기)"),
      sectionSpacer(220, 160),
      body("아래는 일반적으로 활용되는 시작점이며, 실제 유효 여부는 별도 확인이 필요합니다."),
      channelTable,
      captionLine("공개 일반 무역 채널 가이드 (참고용 안내)"),
      sectionSpacer(260, 0),

      sectionHeader("종합 결론 및 방향성", "※ 점수 구간별 등급 + 팀 검토 필수 문구"),
      sectionSpacer(220, 160),
      conclusionTable,
      sectionSpacer(120, 0),
      conclusionNote,
      sectionSpacer(260, 0),

      sectionHeader("데이터 한계", "※ 리스크와 분리하여 한 줄로만 작성"),
      sectionSpacer(220, 160),
      grayBox("관세율 데이터는 조사 시점 기준이며, 향후 변경될 수 있습니다. 일부 보조 지표(물류일수 등)는 확보되지 않아 계산에서 제외되었습니다. \"한국 기업 진출 선례\"는 웹 검색 결과에 의존하므로, 검색되지 않은 사례가 실제로는 존재할 수 있습니다."),
      sectionSpacer(320, 0),

      sectionHeader("산출 근거", "※ 세부 지표 산식 및 API 출처 명시", { num: "A" }),
      sectionSpacer(220, 160),
      new Table({
        width: { size: 9500, type: WidthType.DXA }, columnWidths: [4200, 5300],
        rows: [
          new TableRow({ tableHeader: true, children: [navyHeaderCell("산출 지표", 4200), navyHeaderCell("값 / 산식", 5300)] }),
          new TableRow({ children: [valueCell("Market Opportunity Score", 4200, { fill: ROW_ALT, bold: true }), valueCell("85 / 100", 5300, { fill: ROW_ALT, bold: true, color: INDIGO_DEEP })] }),
          new TableRow({ children: [valueCell("Penetration Opportunity Score", 4200, { bold: true }), valueCell("79 / 100", 5300, { bold: true, color: INDIGO_DEEP })] }),
          new TableRow({ children: [valueCell("Blue Ocean Score (기하평균)", 4200, { fill: ROW_ALT, bold: true }), valueCell("82 / 100  (√(85 × 79) ≈ 82)", 5300, { fill: ROW_ALT, bold: true, color: INDIGO_DEEP })] }),
          new TableRow({ children: [valueCell("Export Gap (글로벌 점유율 − 현지 점유율)", 4200, { bold: true }), valueCell("6.0%p", 5300, { bold: true, color: INDIGO_DEEP })] }),
          new TableRow({ children: [valueCell("3년 연평균 성장률 (CAGR)", 4200, { fill: ROW_ALT, bold: true }), valueCell("12.4%", 5300, { fill: ROW_ALT, bold: true, color: INDIGO_DEEP })] }),
          new TableRow({ children: [valueCell("데이터 출처", 4200, { bold: true }), valueCell("UN Comtrade API, 관세청 API (2026년 기준)", 5300, { bold: true, color: INDIGO_DEEP })] }),
        ],
      }),
      captionLine("Blue Ocean Score 세부 산출 근거 (예시 데이터, 표준 산정식)"),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("blue_ocean_report_sample.docx", buf);
  console.log("done");
});
