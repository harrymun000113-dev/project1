(function () {
  'use strict';
  const paper = document.getElementById('reportPrintArea');
  const viewport = paper.parentElement;
  const fit = () => {
    if (viewport.clientWidth) paper.style.setProperty('--report-preview-scale', Math.min(1, viewport.clientWidth / (210 * 96 / 25.4)));
  };
  if (window.ResizeObserver) new ResizeObserver(fit).observe(viewport);
  window.addEventListener('resize', fit);
  fit();
  let preparing = false;
  window.printCurrentReport = async function () {
    if (document.body.dataset.view !== 'report' || preparing) return;
    preparing = true;
    const button = document.querySelector('.report-print-btn');
    const label = button.textContent;
    button.disabled = true;
    button.textContent = '보고서 준비 중…';
    try {
      // Do not refresh: it clears the evidence and destroys/recreates the chart.
      let pending;
      do { pending = window.reportEvidenceReady; await pending; } while (pending !== window.reportEvidenceReady);
      if (document.body.dataset.view !== 'report') return;
      if (document.getElementById('reportShareDiagnosis').dataset.state === 'error') {
        window.showAppToast('보고서 근거 자료 조회에 실패했습니다. 다시 조회한 후 저장해 주세요.');
        return;
      }
      await document.fonts.ready;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      window.print();
    } finally {
      button.disabled = false;
      button.textContent = label;
      preparing = false;
    }
  };
})();
