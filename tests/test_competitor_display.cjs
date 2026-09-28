const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../blueocean/templates/index.html'), 'utf8');
const start = html.indexOf(' function buildMarketWatch(c)');
const end = html.indexOf(' function normalizeApiResult', start);
const context = vm.createContext({
  currentHsCode: '123456',
  cleanNum: v => typeof v === 'number' && Number.isFinite(v) ? v : null,
  lastYears: () => ({ year: 2024, yoy: null, cagr: null }),
  formatMoney: () => '$100M',
  numOrDash: (v, digits) => v.toFixed(digits),
});
vm.runInContext(html.slice(start, end), context);
vm.runInContext(html.slice(end, html.indexOf(' function render(result,c)', end)), context);
test('risk cards use real fields before and after the insight API response', () => {
  const c = { tariff_rate_pct: 0, ntb_items: ['인증 필요'], competitors: 52.57, fx_change_3y_pct: -7.2 };
  const fallback = context.buildMarketWatch(c);
  assert.match(fallback[0].body, /인증 필요/);
  assert.match(fallback[1].body, /52.57%/);
  assert.match(fallback[1].body, /-7.20%/);
  const result = context.normalizeApiResult({ market_watch: [{ title: '위험', fact: '관세 0%', impact: '인증 확인' }] }, c);
  assert.equal(result.watch[0].desc, '관세 0% 인증 확인');
});
test('competitor KPI displays a percentage with its actual definition', () => {
  const result = context.buildFallback({ competitors: 52.57, export_gap: null, penetration: null });
  const kpi = result.kpis.find(k => k.label === '경쟁국 Top3 점유율');
  assert.equal(kpi.value, '52.57%');
  assert.equal(kpi.note, '한국 제외 · 상위 3개국 합산');
  const missing = context.buildFallback({ competitors: null, export_gap: null, penetration: null });
  assert.equal(missing.kpis.at(-1).value, '미확인');
});
