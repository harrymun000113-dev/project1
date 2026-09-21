/* A-2 3D 헌팅 지구본 (§3.3). globe.gl(Three.js 래퍼)로 서울 -> 타깃국 호를 그린다.
 * globe.gl 스크립트가 어떤 이유로든 로드되지 않아도(오프라인 CDN 차단 등) 나머지
 * 대시보드는 계속 동작해야 하므로, init()에서 window.Globe 유무를 확인한다. */
window.BOFGlobe = (function () {
  "use strict";

  const SEOUL = { lat: 37.5, lng: 127.0 };
  const COLOR_SELECTED = "#ff4d5e";
  const COLOR_DEFAULT = "#3d8bfd";

  let world = null;
  let available = false;

  function init(containerEl) {
    if (typeof window.Globe !== "function") {
      console.warn("[BOFGlobe] globe.gl 라이브러리를 불러오지 못했습니다. 지구본을 건너뜁니다.");
      containerEl.innerHTML =
        '<div class="text-muted small p-3">3D 지구본 라이브러리를 불러오지 못했습니다 (네트워크 확인).</div>';
      available = false;
      return;
    }
    try {
      world = window.Globe()(containerEl)
        .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
        .backgroundColor("rgba(0,0,0,0)")
        .arcColor((d) => d.color)
        .arcDashLength(0.4)
        .arcDashGap(0.15)
        .arcDashAnimateTime(2200)
        .arcStroke(0.5)
        .pointColor((d) => d.color)
        .pointAltitude(0.012)
        .pointRadius(0.4)
        .pointLabel((d) => d.label)
        .onPointClick((d) => window.BOF.emit("target:selected", d.iso3));
      world.pointOfView({ lat: 25, lng: 70, altitude: 2.4 }, 0);
      available = true;
    } catch (e) {
      console.error("[BOFGlobe] 초기화 실패:", e);
      available = false;
    }
  }

  function render(targets, selectedIso3) {
    if (!available || !world) return;
    const valid = targets.filter((t) => typeof t.lat === "number" && typeof t.lon === "number");
    const arcs = valid.map((t) => ({
      startLat: SEOUL.lat,
      startLng: SEOUL.lng,
      endLat: t.lat,
      endLng: t.lon,
      color: t.iso3 === selectedIso3 ? [COLOR_SELECTED, COLOR_SELECTED] : [COLOR_DEFAULT, COLOR_DEFAULT],
    }));
    const points = valid.map((t) => ({
      lat: t.lat,
      lng: t.lon,
      iso3: t.iso3,
      label: t.iso2 + " " + t.name_en,
      color: t.iso3 === selectedIso3 ? COLOR_SELECTED : COLOR_DEFAULT,
    }));
    world.arcsData(arcs).pointsData(points);
  }

  function zoom(factor) {
    if (!available || !world) return;
    const pov = world.pointOfView();
    const altitude = Math.max(0.5, Math.min(4, pov.altitude * factor));
    world.pointOfView({ lat: pov.lat, lng: pov.lng, altitude }, 300);
  }

  function reset() {
    if (!available || !world) return;
    world.pointOfView({ lat: 25, lng: 70, altitude: 2.4 }, 600);
  }

  return { init, render, zoom, reset };
})();
