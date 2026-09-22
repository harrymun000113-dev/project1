/* C-3 Top 20 표 (§3.9). 정렬은 클라이언트에서만 처리하고(§3.10 sort:changed, 재요청 없음),
 * ⬆️/⬇️ 팝오버(§3.9.1)와 경쟁국 팝오버(§3.9.2)는 행 클릭(타깃 선택)과 충돌하지 않도록
 * stopPropagation을 반드시 건다. */
window.BOFRankingTable = (function () {
  "use strict";

  // 정렬 방향: Score/Growth/시장규모는 큰 값이 좋으므로 내림차순, 한국 점유율은 낮을수록
  // 블루오션이므로 오름차순으로 정렬한다(§0.2 '한국 점유율' 정의 — 침투율이 낮을수록 매력적).
  const SORTERS = {
    score: (a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity),
    korea_share_pct: (a, b) => (a.korea_share_pct ?? Infinity) - (b.korea_share_pct ?? Infinity),
    growth: (a, b) => (b.growth.yoy_pct ?? -Infinity) - (a.growth.yoy_pct ?? -Infinity),
    market_size_usd: (a, b) => (b.market_size_usd ?? -Infinity) - (a.market_size_usd ?? -Infinity),
  };

  function growthSymbol(direction) {
    if (direction === "up") return { icon: "⬆️", cls: "up", label: "전년 대비 수입 증가" };
    if (direction === "down") return { icon: "⬇️", cls: "down", label: "전년 대비 수입 감소" };
    return { icon: "–", cls: "flat", label: "증감 정보 없음" };
  }

  // §3.9.1 이상치 경고 — 규칙 기반(백엔드 scoring.flag_growth_outliers)으로 이미 계산된
  // 플래그를 data_flags에서 읽기만 한다. 여기서는 판정하지 않는다.
  function hasGrowthOutlier(row) {
    const flags = row.data_flags || [];
    return flags.includes("growth_outlier_yoy") || flags.includes("growth_outlier_cagr3");
  }

  function buildGrowthPopover(row) {
    const g = row.growth;
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "bof-popover-title";
    title.textContent = "전년 대비 수입 성장률";
    const value = document.createElement("div");
    value.style.fontWeight = "700";
    value.style.fontSize = "1.05rem";
    value.textContent = window.BOF.fmtPct(g.yoy_pct);
    const trail = document.createElement("div");
    trail.className = "text-muted";
    const prevMoney = window.BOF.fmtMoney(g.prev_value_usd, window.BOF.state.currency, window.BOF.state.fxRate);
    const currMoney = window.BOF.fmtMoney(g.curr_value_usd, window.BOF.state.currency, window.BOF.state.fxRate);
    trail.textContent = (g.prev_year ?? "-") + "  " + prevMoney + "  →  " + (g.curr_year ?? "-") + "  " + currMoney;
    wrap.append(title, value, trail);
    if (hasGrowthOutlier(row)) {
      const warn = document.createElement("div");
      warn.className = "bof-popover-warning";
      warn.textContent = "⚠️ 이례적인 수치입니다 (전년도 수입액이 극히 작았을 수 있음 등)";
      wrap.appendChild(warn);
    }
    return wrap;
  }

  function buildCompetitorPopover(row) {
    const c = row.competitors;
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "bof-popover-title";
    title.textContent = "경쟁국 (한국 제외)";
    wrap.appendChild(title);

    (c.top3 || []).forEach((t, i) => {
      const line = document.createElement("div");
      line.className = "bof-popover-row";
      const name = document.createElement("span");
      name.textContent = i + 1 + ". " + (t.name_ko || t.name_en || t.iso3);
      const pct = document.createElement("span");
      pct.textContent = window.BOF.fmtSharePct(t.share_pct);
      line.append(name, pct);
      wrap.appendChild(line);
    });

    wrap.appendChild(document.createElement("hr"));
    const total = document.createElement("div");
    total.className = "bof-popover-row";
    total.style.fontWeight = "700";
    const tName = document.createElement("span");
    tName.textContent = "합계";
    const tVal = document.createElement("span");
    tVal.textContent = window.BOF.fmtSharePct(c.top3_share_pct);
    total.append(tName, tVal);
    wrap.appendChild(total);
    return wrap;
  }

  function render(tbody, top20, sortBy, selectedIso3) {
    tbody.innerHTML = "";
    if (!top20 || !top20.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">표시할 데이터가 없습니다.</td></tr>';
      return;
    }

    const sorted = [...top20].sort(SORTERS[sortBy] || SORTERS.score);

    sorted.forEach((row) => {
      const tr = document.createElement("tr");
      tr.dataset.iso3 = row.iso3;
      if (row.iso3 === selectedIso3) tr.classList.add("selected");
      tr.addEventListener("click", () => window.BOF.emit("target:selected", row.iso3));

      const currency = window.BOF.state.currency;
      const fxRate = window.BOF.state.fxRate;

      const tdRank = document.createElement("td");
      tdRank.textContent = row.rank;

      const tdCountry = document.createElement("td");
      tdCountry.textContent = (row.iso2 || "") + " " + (row.name_en || "");

      const tdScore = document.createElement("td");
      tdScore.textContent = row.score !== null && row.score !== undefined ? Math.round(row.score) : "-";

      const tdGrowth = document.createElement("td");
      const g = growthSymbol(row.growth.direction);
      const growthBtn = document.createElement("button");
      growthBtn.type = "button";
      growthBtn.className = "growth-btn " + g.cls;
      growthBtn.textContent = g.icon;
      growthBtn.setAttribute("aria-label", g.label);
      growthBtn.setAttribute("data-popover-trigger", "1");
      if (g.cls !== "flat") {
        growthBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          window.BOFPopover.toggle(growthBtn, "growth:" + row.iso3, () => buildGrowthPopover(row));
        });
      } else {
        growthBtn.disabled = true;
      }
      tdGrowth.appendChild(growthBtn);
      if (hasGrowthOutlier(row)) {
        const warnBadge = document.createElement("span");
        warnBadge.className = "growth-outlier-badge";
        warnBadge.textContent = "⚠️";
        warnBadge.setAttribute("aria-label", "이례적인 증감률 — 기저효과 등 확인 필요");
        warnBadge.title = "이례적인 증감률 — 기저효과 등 확인 필요";
        tdGrowth.appendChild(warnBadge);
      }

      const tdShare = document.createElement("td");
      tdShare.textContent = window.BOF.fmtSharePct(row.korea_share_pct);

      const tdCompetitors = document.createElement("td");
      const compBtn = document.createElement("button");
      compBtn.type = "button";
      compBtn.className = "competitor-btn";
      compBtn.setAttribute("data-popover-trigger", "1");
      compBtn.textContent = window.BOF.fmtSharePct(row.competitors.top3_share_pct);
      compBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        window.BOFPopover.toggle(compBtn, "competitors:" + row.iso3, () => buildCompetitorPopover(row));
      });
      tdCompetitors.appendChild(compBtn);

      const tdMarket = document.createElement("td");
      tdMarket.textContent = window.BOF.fmtMoney(row.market_size_usd, currency, fxRate);

      tr.append(tdRank, tdCountry, tdScore, tdGrowth, tdShare, tdCompetitors, tdMarket);
      tbody.appendChild(tr);
    });
  }

  return { render };
})();
