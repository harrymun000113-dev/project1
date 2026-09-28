(function () {
  'use strict';
  const results = new Map();
  let activeKey = '';
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  function link(text, url) {
    const a = el('a', text);
    if (/^https?:\/\//i.test(url || '')) { a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    return a;
  }
  async function request(url) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, { signal: controller.signal });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message || '근거 분석 조회에 실패했습니다.');
      return { status: response.status, body };
    } finally { clearTimeout(timer); }
  }
  async function load(hs, iso3) {
    let response = await request('/api/share-diagnosis?' + new URLSearchParams({ hs, iso3 }));
    const job = response.body.job_id;
    const deadline = Date.now() + 120000;
    while (response.status === 202) {
      if (!job) throw new Error('분석 작업 번호가 없습니다.');
      if (Date.now() > deadline) throw new Error('분석이 오래 걸리고 있습니다. 잠시 후 다시 조회해 주세요.');
      await new Promise(resolve => setTimeout(resolve, 1200));
      response = await request('/api/jobs/' + encodeURIComponent(job));
    }
    return response.body;
  }
  function render(box, data) {
    box.replaceChildren();
    box.append(el('p', `${data.country} · HS ${data.hs_code} · ${data.year}년 기준`, 'share-context'));
    if (data.mode === 'demo') box.append(el('p', '데모 데이터입니다. 실제 시장의 원인이나 진출 판단 근거로 사용할 수 없습니다.', 'report-limitation'));
    box.append(el('p', data.summary));
    for (const fact of data.facts || []) {
      const card = el('article', undefined, 'share-evidence');
      card.id = 'share-fact-' + fact.id;
      card.append(el('h4', `${fact.id}. ${fact.title}`));
      card.append(el('p', '확인된 데이터 · ' + fact.observation, 'share-observation'));
      card.append(el('p', '데이터 해석 · ' + fact.interpretation));
      const refs = el('p', '근거: ', 'share-references');
      for (const id of fact.source_ids || []) {
        const a = el('a', `[${id}] `); a.href = '#share-source-' + id; refs.append(a);
      }
      card.append(refs); box.append(card);
    }
    const external = el('section', undefined, 'share-ai');
    window.renderOfficialResearch(external, data.external_research);
    box.append(external, el('h4', '출처 및 조회 조건'));
    for (const source of data.sources || []) {
      const p = el('p', undefined, 'share-source'); p.id = 'share-source-' + source.id;
      p.append(link(`[${source.id}] ${source.publisher} · ${source.title}`, source.url));
      p.append(el('small', source.scope || ''));
      if (source.date) p.append(el('small', `${source.date_label || '기준일'}: ${source.date}`));
      if (source.demo) p.append(el('small', '이 수치는 합성 데모 값이며 아래 기관의 실측값이 아닙니다.'));
      if (source.query_url && !source.demo) p.append(link('동일 조건 API 조회 (접근 권한 필요)', source.query_url));
      box.append(p);
    }
  }
  window.loadReportShareDiagnosis = function (hs, country, generation) {
    const box = document.getElementById('reportShareDiagnosis');
    const key = [hs, country?.id, generation].join(':');
    activeKey = key;
    if (!country || !/^\d{6}$/.test(hs)) { box.textContent = 'HS 코드를 분석하고 국가를 선택해 주세요.'; return; }
    box.textContent = '무역 데이터를 대조하고 외부 공식 자료의 원문·출처를 확인하고 있습니다…';
    if (!results.has(key)) {
      const pending = load(hs, country.id);
      results.set(key, pending);
      pending.catch(() => results.delete(key));
    }
    results.get(key).then(data => { if (activeKey === key) render(box, data); }).catch(error => {
      if (activeKey !== key) return;
      box.replaceChildren(el('p', error.name === 'AbortError' ? '응답 시간이 초과되었습니다.' : error.message));
      const retry = el('button', '다시 조회'); retry.type = 'button';
      retry.onclick = () => window.loadReportShareDiagnosis(hs, country, generation);
      box.append(retry);
    });
  };
})();
