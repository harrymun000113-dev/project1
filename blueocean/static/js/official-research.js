(function () {
  'use strict';
  window.renderOfficialResearch = function (node, research) {
    if (!node) return;
    node.replaceChildren();
    const facts = (research?.facts || []).filter(f => f.text && f.sources?.some(s => /^https:\/\//i.test(s.url)));
    node.hidden = facts.length === 0;
    if (!facts.length) return;
    const heading = document.createElement('h4'); heading.textContent = '외부 공식 자료 · AI 원문 요약'; node.append(heading);
    for (const fact of facts) {
      const article = document.createElement('article'); article.className = 'share-evidence';
      const p = document.createElement('p'); p.textContent = fact.text; article.append(p);
      if (fact.quote) {
        const quote = document.createElement('blockquote'); quote.textContent = '원문 근거: ' + fact.quote;
        quote.style.cssText = 'margin:8px 0;padding-left:10px;border-left:2px solid #bbc9e2;font-size:11px;color:#687c9a';
        article.append(quote);
      }
      for (const source of fact.sources) {
        if (!/^https:\/\//i.test(source.url)) continue;
        const a = document.createElement('a'); a.textContent = source.title + ' · ' + source.publisher;
        a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.style.cssText = 'display:block;color:#315cac;text-decoration:underline;overflow-wrap:anywhere;font-size:11px';
        article.append(a);
      }
      node.append(article);
    }
    if (research.retrieved_at) {
      const stamp = document.createElement('small'); stamp.textContent = '외부 자료 조회일: ' + research.retrieved_at.slice(0, 10); node.append(stamp);
    }
  };
})();
