/* Chart.js 기반 차트 3종: C-2 버블맵, C-4 Export Gap Trend, C-5 환율 2점 그래프.
 * 매 렌더마다 이전 Chart 인스턴스를 destroy 해서 캔버스 재사용 시 메모리 누수/잔상을 막는다. */
window.BOFCharts = (function () {
  "use strict";

  let bubbleChart = null;
  let gapChart = null;
  let fxChart = null;

  function destroy(chart) {
    if (chart) chart.destroy();
  }

  // ── C-2 Global Blue Ocean Map (bubble) ──────────────────────────────
  function renderBubble(canvas, top20, selectedIso3) {
    destroy(bubbleChart);
    if (!canvas || !top20 || !top20.length) return;

    const sizes = top20.map((r) => Math.sqrt(Math.max(r.market_size_usd || 0, 1)));
    const minS = Math.min(...sizes), maxS = Math.max(...sizes);
    const scaleR = (s) => {
      if (maxS === minS) return 14;
      return 6 + ((s - minS) / (maxS - minS)) * 26;
    };

    const points = top20.map((r, i) => ({
      x: r.korea_share_pct ?? 0,
      y: r.potential ?? 0,
      r: scaleR(sizes[i]),
      raw: r,
    }));

    bubbleChart = new Chart(canvas.getContext("2d"), {
      type: "bubble",
      data: {
        datasets: [
          {
            label: "타깃국",
            data: points,
            backgroundColor: points.map((p) =>
              p.raw.iso3 === selectedIso3 ? "rgba(255,77,94,0.75)" : "rgba(61,139,253,0.55)"
            ),
            borderColor: points.map((p) => (p.raw.iso3 === selectedIso3 ? "#ff4d5e" : "#3d8bfd")),
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            title: { display: true, text: "Korea Penetration (%)", color: "#94a1b8" },
            ticks: { color: "#94a1b8" },
            grid: { color: "#232d45" },
          },
          y: {
            title: { display: true, text: "Target Market Potential (0-100)", color: "#94a1b8" },
            ticks: { color: "#94a1b8" },
            grid: { color: "#232d45" },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const r = ctx.raw.raw;
                return [
                  r.iso2 + " " + r.name_en,
                  "Score " + r.score,
                  "시장규모 " + window.BOF.fmtMoney(r.market_size_usd, "USD"),
                ];
              },
            },
          },
        },
        onClick: (evt, elements) => {
          if (!elements.length) return;
          const idx = elements[0].index;
          const iso3 = points[idx].raw.iso3;
          window.BOF.emit("target:selected", iso3);
        },
      },
    });
  }

  // ── C-4 Export Gap Trend ────────────────────────────────────────────
  function renderGapTrend(canvas, gapTrend) {
    destroy(gapChart);
    if (!canvas || !gapTrend || !gapTrend.length) return;

    const labels = gapTrend.map((r) => String(r.year));
    gapChart = new Chart(canvas.getContext("2d"), {
      data: {
        labels,
        datasets: [
          {
            type: "bar",
            label: "Total Import",
            data: gapTrend.map((r) => r.total_import_usd),
            backgroundColor: "rgba(61,139,253,0.55)",
            yAxisID: "y",
          },
          {
            type: "bar",
            label: "Korea Export",
            data: gapTrend.map((r) => r.korea_export_usd),
            backgroundColor: "rgba(51,209,122,0.65)",
            yAxisID: "y",
          },
          {
            type: "line",
            label: "Export Gap (%p)",
            data: gapTrend.map((r) => r.export_gap_pp),
            borderColor: "#ff4d5e",
            backgroundColor: "#ff4d5e",
            yAxisID: "y1",
            tension: 0.25,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            position: "left",
            title: { display: true, text: "USD", color: "#94a1b8" },
            ticks: { color: "#94a1b8" },
            grid: { color: "#232d45" },
          },
          y1: {
            position: "right",
            title: { display: true, text: "Export Gap (%p)", color: "#94a1b8" },
            ticks: { color: "#94a1b8" },
            grid: { display: false },
          },
          x: { ticks: { color: "#94a1b8" }, grid: { display: false } },
        },
        plugins: { legend: { labels: { color: "#e7ecf5" } } },
      },
    });
  }

  // ── C-5 환율 2점 라인 차트 ────────────────────────────────────────────
  function renderFx(canvas, fx) {
    destroy(fxChart);
    if (!canvas || !fx || !fx.now_date || !fx.then_date) return;

    const up = (fx.change_3y_pct || 0) >= 0;
    const color = up ? "#33d17a" : "#ff4d5e";

    fxChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: [fx.then_date + " (3년 전)", fx.now_date + " (현재)"],
        datasets: [
          {
            label: (fx.currency || "") + " -> KRW",
            data: [fx.krw_per_local_then, fx.krw_per_local_now],
            borderColor: color,
            backgroundColor: color,
            pointRadius: 5,
            pointBackgroundColor: color,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { ticks: { color: "#94a1b8" }, grid: { color: "#232d45" } },
          x: { ticks: { color: "#94a1b8" }, grid: { display: false } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => "1 " + (fx.currency || "") + " = " + Number(ctx.raw).toFixed(2) + " KRW",
            },
          },
        },
      },
    });
  }

  return { renderBubble, renderGapTrend, renderFx };
})();
