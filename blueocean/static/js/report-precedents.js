(function () {
  'use strict';
  const cache = new Map();
  let activeKey = '';
  window.loadReportPrecedents = function (hs, country) {
    const box = document.getElementById('reportPrecedentBox');
    const key = hs + ':' + (country?.id || '');
    activeKey = key;
    box.replaceChildren();
    if (!country || !/^\d{6}$/.test(hs)) {
      box.textContent = 'HS 코드를 분석하고 국가를 선택하면 관련 진출 보도를 조회합니다.';
      return;
    }
    box.textContent = country.name_kr + ' · 해당 품목의 한국 기업 진출 관련 보도를 검색 중입니다…';
    if (!cache.has(key)) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 18000);
      const pending = fetch('/api/entry-precedents?' + new URLSearchParams({ hs, iso3: country.id }), { signal: controller.signal })
        .then(async response => {
          const data = await response.json();
          if (!response.ok) throw new Error(data.error?.message || '검색에 실패했습니다.');
          return data;
        }).finally(() => clearTimeout(timer));
      cache.set(key, pending);
      pending.catch(() => cache.delete(key));
    }
    cache.get(key).then(data => {
      if (activeKey !== key) return;
      box.replaceChildren();
      const note = document.createElement('p');
      note.textContent = data.message;
      box.append(note);
      for (const item of data.items || []) {
        if (!/^https?:\/\//i.test(item.url)) continue;
        const article = document.createElement('p');
        const link = document.createElement('a');
        link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.textContent = item.title;
        link.style.cssText = 'text-decoration:underline;font-weight:600;overflow-wrap:anywhere';
        const source = document.createElement('small');
        source.style.display = 'block';
        source.textContent = item.source + ' · ' + item.published_at.slice(0, 10);
        article.append(link, source); box.append(article);
      }
    }).catch(error => {
      if (activeKey !== key) return;
      box.replaceChildren();
      const note = document.createElement('p');
      note.textContent = '진출 보도 조회 실패: ' + (error.name === 'AbortError' ? '응답 시간이 초과되었습니다.' : error.message);
      const retry = document.createElement('button');
      retry.type = 'button'; retry.textContent = '다시 조회';
      retry.onclick = () => window.loadReportPrecedents(hs, country);
      box.append(note, retry);
    });
  };
})();
