/* 페이지 오케스트레이션: 헤더 검색 -> /api/analyze -> 상태 갱신 -> 전 컴포넌트 리렌더 (§3.10). */
(function () {
  "use strict";

  const BOF = window.BOF;
  const detailCache = {}; // iso3 -> /api/country/<iso3>/detail 응답 (같은 국가 재클릭 시 재요청 방지)

  // ── DOM refs ──────────────────────────────────────────────────────────
  const els = {
    searchForm: document.getElementById("hs-search-form"),
    searchInput: document.getElementById("hs-search-input"),
    suggestList: document.getElementById("hs-suggest-list"),
    currencyToggle: document.getElementById("currency-toggle"),
    sortSelect: document.getElementById("rank-sort-select"),
    rankingBody: document.getElementById("ranking-table-body"),
    exportCsvLink: document.getElementById("export-csv-link"),
    exportHtmlLink: document.getElementById("export-html-link"),
    globeCanvas: document.getElementById("globe-canvas"),
    globeOriginLabel: document.getElementById("globe-origin-label"),
    chipBar: document.getElementById("target-chip-bar"),
    hudEmpty: document.getElementById("hud-empty"),
    hudBody: document.getElementById("hud-body"),
    bubbleCanvas: document.getElementById("blue-ocean-bubble-chart"),
    gapCanvas: document.getElementById("export-gap-trend-chart"),
    gapCountryLabel: document.getElementById("gap-trend-country"),
    fxCanvas: document.getElementById("fx-chart"),
    baseYearBadge: document.getElementById("rank-base-year-badge"),
  };

  // ── 초기화 ───────────────────────────────────────────────────────────
  window.BOFGlobe.init(els.globeCanvas);
  loadFxLatest();
  loadScoreSpec();

  els.searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitHs(els.searchInput.value);
  });

  let suggestTimer = null;
  els.searchInput.addEventListener("input", () => {
    clearTimeout(suggestTimer);
    const q = els.searchInput.value.trim();
    if (!q) {
      els.suggestList.classList.add("d-none");
      return;
    }
    suggestTimer = setTimeout(() => fetchSuggest(q), 250);
  });
  document.addEventListener("click", (e) => {
    if (!els.suggestList.contains(e.target) && e.target !== els.searchInput) {
      els.suggestList.classList.add("d-none");
    }
  });

  els.currencyToggle.addEventListener("click", () => {
    const next = BOF.state.currency === "USD" ? "KRW" : "USD";
    BOF.setState({ currency: next });
    els.currencyToggle.dataset.currency = next;
    BOF.emit("currency:changed", next);
    renderMoneyDependent();
  });

  els.sortSelect.addEventListener("change", () => {
    BOF.setState({ sortBy: els.sortSelect.value });
    BOF.emit("sort:changed", els.sortSelect.value);
    renderRankingTable();
  });

  document.getElementById("hud-next").addEventListener("click", () => {
    const top20 = (BOF.state.data && BOF.state.data.top20) || [];
    if (!top20.length) return;
    const order = [...top20].sort((a, b) => a.rank - b.rank);
    const idx = order.findIndex((r) => r.iso3 === BOF.state.selectedIso3);
    const next = order[(idx + 1) % order.length];
    BOF.emit("target:selected", next.iso3);
  });

  document.getElementById("globe-zoom-in").addEventListener("click", () => window.BOFGlobe.zoom(0.75));
  document.getElementById("globe-zoom-out").addEventListener("click", () => window.BOFGlobe.zoom(1.3));
  document.getElementById("globe-reset").addEventListener("click", () => window.BOFGlobe.reset());

  BOF.on("target:selected", onTargetSelected);

  // ── HS 검색 제출 ─────────────────────────────────────────────────────
  function submitHs(raw) {
    const digits = (raw || "").replace(/\D/g, "");
    if (!digits) {
      BOF.toast("HS코드는 숫자로 입력해 주세요.");
      return;
    }
    els.suggestList.classList.add("d-none");
    setLoading(true);
    fetchAnalyze(digits)
      .then((data) => {
        applyAnalyzeResult(digits, data);
      })
      .catch((err) => {
        console.error("[BOF] analyze 실패:", err);
        BOF.toast("분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => setLoading(false));
  }

  function setLoading(isLoading) {
    if (isLoading) {
      els.rankingBody.innerHTML =
        '<tr><td colspan="7" class="text-center text-muted py-4">분석 중… (첫 조회는 다소 걸릴 수 있습니다)</td></tr>';
    }
  }

  function fetchAnalyze(hs6) {
    return fetch("/api/analyze?hs=" + encodeURIComponent(hs6))
      .then((resp) => resp.json().then((body) => ({ status: resp.status, body })))
      .then(({ status, body }) => {
        if (status === 202 && body.job_id) {
          return pollJob(body.job_id, body.hs6_normalized);
        }
        if (body.error && body.error.code === "BAD_HS") {
          throw new Error(body.error.message);
        }
        return body;
      });
  }

  function pollJob(jobId, hs6Normalized) {
    return new Promise((resolve, reject) => {
      const tick = () => {
        fetch("/api/jobs/" + jobId)
          .then((resp) => resp.json().then((body) => ({ status: resp.status, body })))
          .then(({ status, body }) => {
            if (status === 202) {
              setTimeout(tick, 1200);
              return;
            }
            if (status >= 400) {
              reject(new Error((body.error && body.error.message) || "작업 실패"));
              return;
            }
            if (hs6Normalized) body.meta = Object.assign({}, body.meta, { hs6_normalized: true });
            resolve(body);
          })
          .catch(reject);
      };
      tick();
    });
  }

  function applyAnalyzeResult(hs6, data) {
    const normalized = !!(data.hs6_normalized || (data.meta && data.meta.hs6_normalized));
    if (normalized) BOF.toast("6자리로 분석합니다.");

    if (data.error && data.error.code === "NO_DATA") {
      BOF.toast("해당 품목 데이터가 없습니다.");
    }

    const top20 = data.top20 || [];
    const firstIso3 = top20.length ? [...top20].sort((a, b) => a.rank - b.rank)[0].iso3 : null;

    BOF.setState({ hs6, data, selectedIso3: firstIso3 });
    BOF.emit("hs:changed", data);

    renderGlobeOriginLabel(top20.length);
    window.BOFGlobe.render(top20, firstIso3);
    renderChipBar(top20, firstIso3);
    renderRankingTable();
    renderBaseYearBadge(data.meta);
    window.BOFCharts.renderBubble(els.bubbleCanvas, top20, firstIso3);
    updateExportLinks(hs6);

    if (firstIso3) {
      onTargetSelected(firstIso3);
    } else {
      showEmptyHud();
    }
  }

  // ── 타깃 선택 (§3.10 target:selected) ────────────────────────────────
  function onTargetSelected(iso3) {
    BOF.setState({ selectedIso3: iso3 });
    const row = BOF.findTarget(iso3);
    if (!row) return;

    renderHud(row);
    const top20 = (BOF.state.data && BOF.state.data.top20) || [];
    window.BOFGlobe.render(top20, iso3);
    highlightChip(iso3);
    renderRankingTable();
    window.BOFCharts.renderBubble(els.bubbleCanvas, top20, iso3);
    renderTradeBarriers(row);
    renderFxCard(row);

    loadCountryDetail(BOF.state.hs6, iso3);
  }

  function loadCountryDetail(hs6, iso3) {
    els.gapCountryLabel.textContent = BOF.findTarget(iso3)?.name_en || iso3;

    if (detailCache[iso3]) {
      applyCountryDetail(iso3, detailCache[iso3]);
      return;
    }
    fetch("/api/country/" + iso3 + "/detail?hs=" + encodeURIComponent(hs6))
      .then((resp) => resp.json())
      .then((body) => {
        if (body.error) {
          console.warn("[BOF] country detail error:", body.error);
          return;
        }
        detailCache[iso3] = body;
        if (BOF.state.selectedIso3 === iso3) applyCountryDetail(iso3, body);
      })
      .catch((e) => console.warn("[BOF] country detail 요청 실패:", e));
  }

  function applyCountryDetail(iso3, body) {
    window.BOFCharts.renderGapTrend(els.gapCanvas, body.gap_trend);
    renderAiInsight(body.insight, BOF.findTarget(iso3));
  }

  // ── HUD ──────────────────────────────────────────────────────────────
  function showEmptyHud() {
    els.hudEmpty.classList.remove("d-none");
    els.hudBody.classList.add("d-none");
  }

  function renderHud(row) {
    els.hudEmpty.classList.add("d-none");
    els.hudBody.classList.remove("d-none");

    document.getElementById("hud-rank-badge").textContent =
      "TARGET #" + row.rank + (row.rank === 1 ? " (최우선)" : "");
    document.getElementById("hud-iso2-badge").textContent = row.iso2 || "--";
    document.getElementById("hud-name-en").textContent = row.name_en || "-";
    document.getElementById("hud-name-ko").textContent = row.name_ko ? "(" + row.name_ko + ")" : "";
    const hsDesc = (BOF.state.data && BOF.state.data.meta && BOF.state.data.meta.hs_desc) || "";
    document.getElementById("hud-item-line").textContent = "HS " + BOF.state.hs6 + " " + hsDesc;
    document.getElementById("hud-score").textContent = row.score !== null ? Math.round(row.score) : "-";
    document.getElementById("hud-potential").textContent = row.potential !== null ? row.potential.toFixed(1) : "-";
    document.getElementById("hud-korea-share").textContent = BOF.fmtSharePct(row.korea_share_pct);
    const gapEl = document.getElementById("hud-gap");
    gapEl.textContent = BOF.fmtPct(row.export_gap_pp) + "p";
    gapEl.style.color = (row.export_gap_pp || 0) > 0 ? "#ff4d5e" : "#33d17a";
  }

  // ── 타깃 칩 바 ────────────────────────────────────────────────────────
  function renderChipBar(top20, selectedIso3) {
    els.chipBar.innerHTML = "";
    [...top20]
      .sort((a, b) => a.rank - b.rank)
      .slice(0, 6)
      .forEach((row) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "target-chip" + (row.iso3 === selectedIso3 ? " selected" : "");
        chip.dataset.iso3 = row.iso3;
        chip.textContent = "[" + row.iso2 + "] " + row.name_ko + " " + BOF.fmtPct(row.export_gap_pp) + "p";
        chip.addEventListener("click", () => BOF.emit("target:selected", row.iso3));
        els.chipBar.appendChild(chip);
      });
  }

  function highlightChip(iso3) {
    els.chipBar.querySelectorAll(".target-chip").forEach((chip) => {
      chip.classList.toggle("selected", chip.dataset.iso3 === iso3);
    });
  }

  function renderGlobeOriginLabel(n) {
    els.globeOriginLabel.textContent =
      "ORIGIN: SEOUL, KOREA (37.5°N, 127.0°E) → HUNTING " + Math.min(n, 6) + " GLOBAL TARGETS";
  }

  // ── AI Insight ───────────────────────────────────────────────────────
  function renderAiInsight(insight, row) {
    if (!insight || !row) return;
    document.getElementById("ai-insight-country").textContent = row.name_en || "-";
    document.getElementById("ai-insight-body").textContent = insight.body || "";
    document.getElementById("ai-insight-action").textContent = insight.action || "";
    document.getElementById("ai-insight-target").textContent =
      "Target: " + (row.name_en || "-") + (row.name_ko ? " (" + row.name_ko + ")" : "");

    const chipsWrap = document.getElementById("ai-insight-chips");
    chipsWrap.innerHTML = "";
    const chips = [
      { label: "Export Gap", value: BOF.fmtPct(row.export_gap_pp) + "p" },
      { label: "YoY 성장률", value: BOF.fmtPct(row.growth.yoy_pct) },
      { label: "경쟁국 Top3 합계", value: (row.competitors.top3_share_pct ?? "-") + "%" },
    ];
    chips.forEach((c) => {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = c.label + " " + c.value;
      chipsWrap.appendChild(badge);
    });
  }

  // ── Trade Barriers (C-1) ─────────────────────────────────────────────
  function renderTradeBarriers(row) {
    document.getElementById("tb-country-label").textContent = row.name_en || "-";
    const b = row.barriers || {};
    const failed = document.getElementById("tb-failed");
    const tariffBlock = document.getElementById("tb-tariff-block");

    if (b.tariff_rate_pct === null || b.tariff_rate_pct === undefined) {
      failed.classList.remove("d-none");
    } else {
      failed.classList.add("d-none");
    }
    tariffBlock.style.opacity = b.tariff_rate_pct === null ? "0.5" : "1";

    document.getElementById("tb-tariff-rate").textContent = BOF.fmtSharePct(b.tariff_rate_pct);
    const typeBadge = document.getElementById("tb-tariff-type");
    typeBadge.textContent = b.tariff_type || "";
    document.getElementById("tb-tariff-sub").textContent = "한국산 HS " + BOF.state.hs6 + " 적용세율";
    document.getElementById("tb-tariff-score").textContent = row.score_breakdown ? row.score_breakdown.tariff : "-";
    document.getElementById("tb-fetched-at").textContent = b.fetched_at ? b.fetched_at.slice(0, 10) : "-";

    const ntbList = document.getElementById("tb-ntb-list");
    ntbList.innerHTML = "";
    document.getElementById("tb-ntb-count").textContent = b.ntb_count || 0;
    const items = b.ntb_items || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "text-muted";
      li.textContent = "확인된 비관세 장벽 없음";
      ntbList.appendChild(li);
    } else {
      items.slice(0, 5).forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item;
        ntbList.appendChild(li);
      });
    }
  }

  // ── FX Rate (C-5) ────────────────────────────────────────────────────
  function renderFxCard(row) {
    const fx = row.fx || {};
    const currency = fx.currency || "-";
    document.getElementById("fx-pair-label").textContent = currency + " ↔ KRW";
    const sourceBadge = document.getElementById("fx-source-badge");
    sourceBadge.textContent = fx.source || "N/A";

    const missing = fx.change_3y_pct === null || fx.change_3y_pct === undefined;
    document.getElementById("fx-missing").classList.toggle("d-none", !missing);

    document.getElementById("fx-summary-value").textContent =
      fx.krw_per_local_now !== null && fx.krw_per_local_now !== undefined
        ? "1 " + currency + " = " + Number(fx.krw_per_local_now).toLocaleString("ko-KR", { maximumFractionDigits: 1 }) + " KRW"
        : "-";
    document.getElementById("fx-summary-date").textContent = fx.now_date ? fx.now_date + " 고시" : "-";

    const changeBadge = document.getElementById("fx-change-badge");
    const changeDesc = document.getElementById("fx-change-desc");
    if (!missing) {
      const up = fx.change_3y_pct >= 0;
      changeBadge.textContent = BOF.fmtPct(fx.change_3y_pct);
      changeBadge.className = "badge fx-change-badge " + (up ? "up" : "down");
      changeDesc.textContent = up ? "현지통화 강세 · 한국산 가격경쟁력 ↑" : "현지통화 약세 · 한국산 가격경쟁력 ↓";
    } else {
      changeBadge.textContent = "-";
      changeBadge.className = "badge fx-change-badge";
      changeDesc.textContent = "";
    }

    document.getElementById("fx-score").textContent = row.score_breakdown ? row.score_breakdown.fx_3y : "-";
    document.getElementById("fx-usd-krw-row").textContent =
      "USD/KRW " + (BOF.state.fxRate ? Math.round(BOF.state.fxRate).toLocaleString("ko-KR") : "-");

    window.BOFCharts.renderFx(els.fxCanvas, fx);
  }

  // ── 통화 토글 / 정렬 변경 시 재렌더 (재요청 없음, §3.10) ────────────────
  function renderMoneyDependent() {
    renderRankingTable();
    const row = BOF.findTarget(BOF.state.selectedIso3);
    if (row) renderHud(row);
  }

  function renderRankingTable() {
    window.BOFRankingTable.render(
      els.rankingBody,
      (BOF.state.data && BOF.state.data.top20) || [],
      BOF.state.sortBy,
      BOF.state.selectedIso3
    );
  }

  // 무역 통계는 각국 정부 보고가 1~3년 걸리는 게 흔해서, 기준연도가 현재 연도보다
  // 몇 년 뒤처지는 게 정상이다 — 사용자가 헷갈리지 않게 어느 연도 기준인지 항상 보여준다.
  function renderBaseYearBadge(meta) {
    if (!meta || !meta.base_year) {
      els.baseYearBadge.classList.add("d-none");
      return;
    }
    els.baseYearBadge.textContent = "기준연도 " + meta.base_year;
    els.baseYearBadge.classList.remove("d-none");
  }

  // ── HS 자동완성 ──────────────────────────────────────────────────────
  function fetchSuggest(q) {
    fetch("/api/hs/suggest?q=" + encodeURIComponent(q))
      .then((resp) => resp.json())
      .then((body) => {
        const items = body.items || [];
        els.suggestList.innerHTML = "";
        if (!items.length) {
          els.suggestList.classList.add("d-none");
          return;
        }
        items.forEach((item) => {
          const a = document.createElement("button");
          a.type = "button";
          a.className = "list-group-item list-group-item-action";
          a.textContent = item.hs6 + " — " + item.desc_ko;
          a.addEventListener("click", () => {
            els.searchInput.value = item.hs6;
            els.suggestList.classList.add("d-none");
            submitHs(item.hs6);
          });
          els.suggestList.appendChild(a);
        });
        els.suggestList.classList.remove("d-none");
      })
      .catch(() => els.suggestList.classList.add("d-none"));
  }

  // ── 헤더 USD/KRW 토글용 환율 ─────────────────────────────────────────
  function loadFxLatest() {
    fetch("/api/fx/latest")
      .then((resp) => resp.json())
      .then((body) => {
        if (body.usd_krw) BOF.setState({ fxRate: body.usd_krw });
      })
      .catch((e) => console.warn("[BOF] fx/latest 요청 실패:", e));
  }

  // ── 평가기준 모달 (§3.1, SCORE_SPEC 단일 원천) ──────────────────────
  function loadScoreSpec() {
    fetch("/api/score-spec")
      .then((resp) => resp.json())
      .then((body) => {
        const tbody = document.getElementById("score-spec-table-body");
        tbody.innerHTML = "";
        (body.items || []).forEach((item, i) => {
          const tr = document.createElement("tr");
          const direction = item.higher_is_better ? "높을수록 좋음" : "낮을수록 좋음";
          tr.innerHTML =
            "<td>" + (i + 1) + "</td><td>" + item.label + "</td><td class='text-end'>" + item.weight +
            "</td><td>" + direction + "</td><td>" + item.column + "</td>";
          tbody.appendChild(tr);
        });
      })
      .catch((e) => console.warn("[BOF] score-spec 요청 실패:", e));
  }

  // ── Export 링크 ──────────────────────────────────────────────────────
  function updateExportLinks(hs6) {
    els.exportCsvLink.href = "/api/export.csv?hs=" + encodeURIComponent(hs6);
    els.exportHtmlLink.href = "/api/export.html?hs=" + encodeURIComponent(hs6);
  }
})();
