/* 전역 상태 · 이벤트 버스 (§3.10). 모든 컴포넌트는 BOF.state를 직접 읽고,
 * BOF.on(...)으로 이벤트를 구독하며, 상태를 바꿀 때는 반드시 BOF.setState를 거친다. */
window.BOF = (function () {
  "use strict";

  const state = {
    hs6: null,
    selectedIso3: null,
    currency: "USD", // "USD" | "KRW"
    fxRate: null,     // USD -> KRW
    sortBy: "score",
    data: null,       // 최근 /api/analyze 응답
  };

  const listeners = {};

  function on(event, fn) {
    (listeners[event] = listeners[event] || []).push(fn);
  }

  function emit(event, payload) {
    (listeners[event] || []).forEach((fn) => {
      try {
        fn(payload);
      } catch (e) {
        console.error("[BOF] listener error for " + event + ":", e);
      }
    });
  }

  function setState(patch) {
    Object.assign(state, patch);
  }

  function findTarget(iso3) {
    if (!state.data || !Array.isArray(state.data.top20)) return null;
    return state.data.top20.find((r) => r.iso3 === iso3) || null;
  }

  function toast(message) {
    const root = document.getElementById("toast-root");
    if (!root) {
      console.warn("[BOF] toast root missing:", message);
      return;
    }
    const el = document.createElement("div");
    el.className = "toast align-items-center text-bg-dark border-0";
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="d-flex"><div class="toast-body">' +
      message +
      '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    root.appendChild(el);
    try {
      const t = new bootstrap.Toast(el, { delay: 3500 });
      t.show();
      el.addEventListener("hidden.bs.toast", () => el.remove());
    } catch (e) {
      // Bootstrap 미로드 환경 대비 (테스트 등)
      setTimeout(() => el.remove(), 3500);
    }
  }

  function fmtMoney(usd, currency, fxRate) {
    if (usd === null || usd === undefined || Number.isNaN(usd)) return "-";
    if (currency === "KRW" && fxRate) {
      const krw = usd * fxRate;
      return "₩" + Math.round(krw).toLocaleString("ko-KR");
    }
    const abs = Math.abs(usd);
    if (abs >= 1e9) return "$" + (usd / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return "$" + (usd / 1e6).toFixed(1) + "M";
    if (abs >= 1e3) return "$" + (usd / 1e3).toFixed(1) + "K";
    return "$" + usd.toFixed(0);
  }

  function fmtPct(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    const d = digits === undefined ? 1 : digits;
    const sign = v > 0 ? "+" : "";
    return sign + v.toFixed(d) + "%";
  }

  return { state, on, emit, setState, findTarget, toast, fmtMoney, fmtPct };
})();
