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
    exportDocxLink: document.getElementById("export-docx-link"),
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
    portfolioBanner: document.getElementById("portfolio-advice-banner"),
    portfolioText: document.getElementById("portfolio-advice-text"),
    analysisView: document.getElementById("analysis-view"),
    trademapView: document.getElementById("trademap-view"),
    trademapIframe: document.getElementById("trademap-iframe"),
    trademapTabLink: document.getElementById("trademap-tab-link"),
    dashboardTabLink: document.getElementById("dashboard-tab-link"),
    trademapBack: document.getElementById("trademap-back"),
  };

  // ── TradeMap 패널 (헤더/히어로는 유지, 아랫부분만 같은 페이지에서 전환) ──
  let trademapLoaded = false;

  function sendHsToTradeMap() {
    if (!trademapLoaded || !BOF.state.hs6 || !els.trademapIframe.contentWindow) return;
    els.trademapIframe.contentWindow.postMessage(
      { source: "blue-ocean-finder", type: "hs-search", hs: BOF.state.hs6 },
      window.location.origin
    );
  }

  function showTradeMap() {
    els.analysisView.classList.add("d-none");
    els.trademapView.classList.remove("d-none");
    if (!els.trademapIframe.src) {
      els.trademapIframe.addEventListener(
        "load",
        () => {
          trademapLoaded = true;
          sendHsToTradeMap();
        },
        { once: true }
      );
      els.trademapIframe.src = "/trademap";
    } else {
      sendHsToTradeMap();
    }
  }

  function showAnalysis() {
    els.trademapView.classList.add("d-none");
    els.analysisView.classList.remove("d-none");
  }

  els.trademapTabLink.addEventListener("click", (e) => {
    e.preventDefault();
    showTradeMap();
  });
  els.dashboardTabLink.addEventListener("click", () => showAnalysis());
  els.trademapBack.addEventListener("click", showAnalysis);
  BOF.on("hs:changed", sendHsToTradeMap);

  // ── 모달 닫기 안전장치 (평가기준/수식 명세) ──────────────────────────
  // data-bs-dismiss 버튼이 Bootstrap 인스턴스 초기화 문제 등으로 반응하지 않을 때,
  // 새로고침 없이도 항상 닫히도록 수동으로도 모달/백드롭을 제거한다.
  function forceCloseModal(modalEl) {
    if (!modalEl) return;
    // Bootstrap의 hide()는 transitionend 이벤트를 기다리다 걸리면 영영 안 끝날 수 있으므로
    // (실제로 이 증상의 원인이었다) best-effort로만 호출하고, 실제 DOM 정리는 항상
    // 아래에서 동기적으로·무조건 수행한다. 이미 닫힌 모달에 또 호출해도 안전(idempotent)하다.
    try {
      const inst = window.bootstrap && bootstrap.Modal.getInstance(modalEl);
      if (inst) inst.hide();
    } catch (e) {
      // 무시하고 아래 수동 정리로 진행
    }
    modalEl.classList.remove("show");
    modalEl.removeAttribute("style"); // Bootstrap이 남겼을 수 있는 inline display:block 제거
    modalEl.setAttribute("aria-hidden", "true");
    modalEl.removeAttribute("aria-modal");
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
    document.querySelectorAll(".modal-backdrop").forEach((b) => b.remove());
  }

  document.addEventListener("click", (e) => {
    const dismissBtn = e.target.closest('[data-bs-dismiss="modal"]');
    if (dismissBtn) {
      forceCloseModal(dismissBtn.closest(".modal"));
      return;
    }
    // 바깥(백드롭) 클릭으로 닫기: 모달 오버레이 자체를 직접 클릭했을 때만 (다이얼로그 내부 클릭 제외)
    if (e.target.classList.contains("modal") && e.target.classList.contains("show")) {
      forceCloseModal(e.target);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal.show").forEach(forceCloseModal);
    }
  });

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

  // 국가를 아직 고르지 않은 상태(비활성)에서 눌러도 아무 반응이 없어 "고장난 것처럼" 보이므로,
  // 그 경우만 토스트로 이유를 알려주고 실제 이동은 막는다. 활성 상태일 때는 막지 않고
  // 평범한 <a href> 다운로드로 흘려보낸다.
  // 주의: Bootstrap의 진짜 `.disabled` 클래스는 pointer-events:none을 걸어서 클릭 이벤트
  // 자체가 이 요소까지 도달하지 못한다(그래서 예전엔 눌러도 토스트조차 안 떴다) — 그래서
  // 여기서는 우리가 만든 `.is-disabled`만 쓰고 pointer-events는 항상 살려 둔다.
  els.exportDocxLink.addEventListener("click", (e) => {
    if (els.exportDocxLink.classList.contains("is-disabled")) {
      e.preventDefault();
      BOF.toast("먼저 Top 20 표에서 국가를 선택해 주세요.");
    }
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

  // 지금 화면에 반영해야 할 "가장 최근 검색"이 몇 번째 검색인지 추적한다. 검색 A 진행 중에
  // 검색 B를 시작하면(예: 실API라 느린 첫 검색이 끝나기 전에 다른 HS코드로 다시 검색),
  // A가 나중에 응답이 와도 이미 낡은 검색이므로 화면을 덮어쓰면 안 된다 — 이 토큰이 그 판단 기준이다.
  let activeSearchToken = 0;

  // ── HS 검색 제출 ─────────────────────────────────────────────────────
  function submitHs(raw) {
    const digits = (raw || "").replace(/\D/g, "");
    if (!digits) {
      BOF.toast("HS코드는 숫자로 입력해 주세요.");
      return;
    }
    els.suggestList.classList.add("d-none");
    const token = ++activeSearchToken;
    setLoading(true);
    fetchAnalyze(digits, token)
      .then((data) => {
        if (token !== activeSearchToken) return;  // 그 사이 다른 검색이 시작됨 -> 이 결과는 버린다
        applyAnalyzeResult(digits, data);
      })
      .catch((err) => {
        if (token !== activeSearchToken) return;
        console.error("[BOF] analyze 실패:", err);
        BOF.toast("분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => {
        if (token === activeSearchToken) setLoading(false);
      });
  }

  function setLoading(isLoading) {
    if (isLoading) {
      els.rankingBody.innerHTML =
        '<tr><td colspan="7" class="text-center text-muted py-4">분석 중… (첫 조회는 다소 걸릴 수 있습니다)</td></tr>';
    }
  }

  // fetch()는 기본적으로 타임아웃이 없어서, 서버가 요청 도중 재시작되는 등으로 응답이
  // 영영 안 오면 폴링 전체가 새로고침 전까지 무한 대기에 빠진다 — 그 방지용 래퍼.
  const FETCH_TIMEOUT_MS = 10000;
  function fetchWithTimeout(url, ms) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ms || FETCH_TIMEOUT_MS);
    return fetch(url, { signal: controller.signal }).finally(() => clearTimeout(timer));
  }

  function fetchAnalyze(hs6, token) {
    return fetchWithTimeout("/api/analyze?hs=" + encodeURIComponent(hs6))
      .then((resp) => resp.json().then((body) => ({ status: resp.status, body })))
      .then(({ status, body }) => {
        if (status === 202 && body.job_id) {
          return pollJob(body.job_id, body.hs6_normalized, token);
        }
        if (body.error && body.error.code === "BAD_HS") {
          throw new Error(body.error.message);
        }
        return body;
      });
  }

  function pollJob(jobId, hs6Normalized, token) {
    const MAX_RETRIES = 5; // 타임아웃/네트워크 순단이 연속 이 횟수 넘게 나야 진짜로 포기한다
    let retries = 0;
    return new Promise((resolve, reject) => {
      const tick = () => {
        if (token !== activeSearchToken) {
          // 이미 다른 검색으로 넘어갔다 — 화면에 쓰이지 않을 결과를 계속 폴링해 서버에
          // 불필요한 요청을 보내지 않도록 여기서 멈춘다.
          reject(new Error("superseded"));
          return;
        }
        fetchWithTimeout("/api/jobs/" + jobId)
          .then((resp) => resp.json().then((body) => ({ status: resp.status, body })))
          .then(({ status, body }) => {
            retries = 0; // 정상 응답을 받았으면 재시도 카운트 리셋
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
          .catch((err) => {
            // 타임아웃·연결 끊김(개발 서버 재시작 등)은 작업 실패로 바로 단정하지 않고
            // 잠깐 쉬었다가 같은 job_id로 재시도한다. 반복해서 실패하면 그때 포기한다.
            if (token !== activeSearchToken) {
              reject(err);
              return;
            }
            retries += 1;
            if (retries > MAX_RETRIES) {
              reject(err);
              return;
            }
            setTimeout(tick, 2000);
          });
      };
      tick();
    });
  }

  // ── 분석 완료 음성 안내 ───────────────────────────────────────────────
  // 분석이 몇 분씩 걸릴 수 있어(§tariff/trends 크롤링), 다른 작업 하다가도 끝난 걸
  // 바로 알 수 있게 완료 시 TTS로 알려준다. 음성 합성을 지원 안 하는 환경이면 조용히 무시.

  // 브라우저마다 설치된 음성 목록이 다르고, 크롬 계열은 getVoices()가 비동기로(첫 호출 시
  // 빈 배열) 채워지는 경우가 많아 voiceschanged 이벤트가 온 뒤에도 다시 찾을 수 있게 캐싱한다.
  let cachedKoreanVoice = null;
  let koreanVoiceResolved = false;

  // 이름에 여성 목소리로 알려진 것부터 우선순위를 둔다 (Windows: Heami/SunHi,
  // macOS/iOS: Yuna, Chrome: Google 한국의 — 셋 다 기본이 여성 음성이다).
  const FEMALE_VOICE_HINTS = ["heami", "sunhi", "yuna", "google 한국", "female", "여성"];

  function pickKoreanVoice() {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    const korean = voices.filter((v) => (v.lang || "").toLowerCase().startsWith("ko"));
    if (!korean.length) return null;
    const byHint = korean.find((v) =>
      FEMALE_VOICE_HINTS.some((hint) => (v.name || "").toLowerCase().includes(hint))
    );
    return byHint || korean[0];
  }

  if (window.speechSynthesis) {
    window.speechSynthesis.addEventListener("voiceschanged", () => {
      cachedKoreanVoice = pickKoreanVoice();
      koreanVoiceResolved = true;
    });
  }

  function announceDone(text) {
    try {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel(); // 이전에 남아있던 안내가 있으면 정리하고 새로 말한다
      if (!koreanVoiceResolved) {
        cachedKoreanVoice = pickKoreanVoice();
        koreanVoiceResolved = true; // 아직 못 찾았어도 다음 voiceschanged에서 다시 채워짐
      }
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = "ko-KR";
      if (cachedKoreanVoice) utter.voice = cachedKoreanVoice;
      // 상큼·발랄한 톤: 높은 피치 + 통통 튀는 빠르기
      utter.pitch = 1.4;
      utter.rate = 1.12;
      utter.volume = 1.0;
      window.speechSynthesis.speak(utter);
    } catch (e) {
      console.warn("[BOF] 음성 안내 실패:", e);
    }
  }

  function applyAnalyzeResult(hs6, data) {
    const normalized = !!(data.hs6_normalized || (data.meta && data.meta.hs6_normalized));
    if (normalized) BOF.toast("6자리로 분석합니다.");

    if (data.error && data.error.code === "NO_DATA") {
      BOF.toast("해당 품목 데이터가 없습니다.");
    }

    const top20 = data.top20 || [];
    const firstIso3 = top20.length ? [...top20].sort((a, b) => a.rank - b.rank)[0].iso3 : null;

    announceDone(
      top20.length
        ? "wow!! HS " + hs6 + " 분석이 드디어 끝났어요!! 결과 확인해 보세요!!"
        : "HS " + hs6 + " 분석은 끝났는데, 아쉽게도 데이터가 없어요."
    );

    BOF.setState({ hs6, data, selectedIso3: firstIso3 });
    BOF.emit("hs:changed", data);

    renderGlobeOriginLabel(top20.length);
    window.BOFGlobe.render(top20, firstIso3);
    renderChipBar(top20, firstIso3);
    renderRankingTable();
    renderBaseYearBadge(data.meta);
    renderPortfolioAdvice(data);
    window.BOFCharts.renderBubble(els.bubbleCanvas, top20, firstIso3);
    updateExportLinks(hs6);
    updateExportDocxLink();  // 결과가 0건이면 이전 검색의 링크가 남아있지 않도록 여기서도 갱신

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
    updateExportDocxLink();

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

  // ── AI Insight (§3.4.2 콘텐츠 블록) ────────────────────────────────────
  function renderAiInsight(insight, row) {
    if (!insight || !row) return;
    document.getElementById("ai-insight-country").textContent = row.name_en || "-";
    document.getElementById("ai-insight-body").textContent = insight.why_market || "";
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

    renderInsightReference(insight.reference);
    renderInsightList("ai-insight-contacts-block", "ai-insight-contacts", insight.contacts, (c) =>
      (c.type ? "[" + c.type + "] " : "") + (c.name || "") + (c.note ? " — " + c.note : "")
    );
    renderInsightList("ai-insight-timeline-block", "ai-insight-timeline", insight.prep_timeline, (t) =>
      (t.due ? t.due + " — " : "") + (t.milestone || "")
    );
    renderInsightRisks(insight.risks);
    renderInsightList("ai-insight-gov-block", "ai-insight-gov", insight.gov_programs, (g) =>
      (g.name || "") + (g.note ? " — " + g.note : "")
    );

    const limitationEl = document.getElementById("ai-insight-limitation");
    if (insight.limitation) {
      limitationEl.textContent = "한계점: " + insight.limitation;
      limitationEl.classList.remove("d-none");
    } else {
      limitationEl.classList.add("d-none");
    }
  }

  // 레퍼런스(선례) 블록 — 선례가 있으면 사례를, 없으면 "왜 없는지" 사유를 보여준다 (§3.4.2 #4).
  function renderInsightReference(reference) {
    const block = document.getElementById("ai-insight-reference-block");
    const textEl = document.getElementById("ai-insight-reference");
    if (!reference || (!reference.exists && !reference.reason_if_none)) {
      block.classList.add("d-none");
      return;
    }
    if (reference.exists) {
      textEl.textContent = (reference.examples || []).join(", ") || "선례가 확인되었습니다.";
    } else {
      textEl.textContent = reference.reason_if_none || "아직 확인된 선례가 없습니다.";
    }
    block.classList.remove("d-none");
  }

  // 접촉 채널·준비 타임라인·정부지원사업처럼 "항목 배열 -> <li> 목록" 형태로 그리는 블록 공통 처리.
  // 배열이 비어 있으면 블록 자체를 숨긴다 — 빈 placeholder를 보여주지 않는다는 §3.4.2 원칙.
  function renderInsightList(blockId, listId, items, formatter) {
    const block = document.getElementById(blockId);
    const listEl = document.getElementById(listId);
    listEl.innerHTML = "";
    if (!items || !items.length) {
      block.classList.add("d-none");
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = formatter(item);
      listEl.appendChild(li);
    });
    block.classList.remove("d-none");
  }

  // 리스크 블록 — 항목마다 심각도(상/중/하) 배지를 붙인다 (§3.4.2 #7).
  function renderInsightRisks(risks) {
    const block = document.getElementById("ai-insight-risks-block");
    const listEl = document.getElementById("ai-insight-risks");
    listEl.innerHTML = "";
    if (!risks || !risks.length) {
      block.classList.add("d-none");
      return;
    }
    const SEVERITY_LABEL = { high: "상", mid: "중", low: "하" };
    risks.forEach((r) => {
      const li = document.createElement("li");
      const badge = document.createElement("span");
      badge.className = "risk-severity-badge " + (r.severity || "");
      badge.textContent = SEVERITY_LABEL[r.severity] || "-";
      const text = document.createElement("span");
      text.textContent = " " + (r.note || "");
      li.append(badge, text);
      listEl.appendChild(li);
    });
    block.classList.remove("d-none");
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

  // ── 종합 조언 배너 (§3.9.0) — 품목(hs6) 단위로만 갱신, 국가 클릭으로는 안 바뀜 ──
  function renderPortfolioAdvice(data) {
    const advice = data && data.portfolio_advice;
    if (!advice || !advice.reason) {
      els.portfolioBanner.classList.add("d-none");
      return;
    }
    els.portfolioText.textContent = advice.reason;
    els.portfolioBanner.classList.remove("d-none");
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

  // Word 보고서는 국가 1개 단위라 hs6뿐 아니라 선택된 국가(selectedIso3)도 필요하다 —
  // 국가를 선택하기 전에는 비활성 상태로 둔다.
  function updateExportDocxLink() {
    const hs6 = BOF.state.hs6;
    const iso3 = BOF.state.selectedIso3;
    if (!hs6 || !iso3) {
      els.exportDocxLink.classList.add("is-disabled");
      els.exportDocxLink.setAttribute("aria-disabled", "true");
      els.exportDocxLink.href = "#";
      return;
    }
    els.exportDocxLink.href = "/api/export.docx?hs=" + encodeURIComponent(hs6) + "&iso3=" + encodeURIComponent(iso3);
    els.exportDocxLink.classList.remove("is-disabled");
    els.exportDocxLink.removeAttribute("aria-disabled");
  }
})();
