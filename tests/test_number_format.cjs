const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../blueocean/templates/index.html'), 'utf8');
const source = html.slice(html.indexOf('    function numOrDash('), html.indexOf('    function mapAnalyzeRowToCountry('));
const context = vm.createContext({});
vm.runInContext(source, context);
vm.runInContext(html.slice(html.indexOf('    function formatKoreaImport('), html.indexOf('    function setCurrency(')), context);
test('import amount displays original dollars, zero, missing data, and KRW conversion', () => {
  context.currentCurrency = 'USD';
  assert.equal(context.formatKoreaImport(1234.56), '$1,234.56');
  assert.equal(context.formatKoreaImport(0), '$0');
  assert.equal(context.formatKoreaImport(.001), '$0.001');
  assert.equal(context.formatKoreaImport(null), '—');
  assert.equal(context.formatKoreaImport(undefined), '—');
  context.currentCurrency = 'KRW';
  context.usdToKrw = 1300;
  assert.equal(context.formatKoreaImport(100), '약 ₩130,000');
});
test('nonzero values retain a visible significant digit', () => {
  for (const [value, expected] of [[.01234, '0.01'], [.00049, '0.0005'], [.0000001234, '0.0000001'], [-.00049, '-0.0005']]) {
    assert.equal(context.numOrDash(value, 1), expected);
  }
});
test('ordinary numbers, actual zero, and missing values stay distinct', () => {
  assert.equal(context.numOrDash(7.89, 1), '7.9');
  assert.equal(context.numOrDash(0, 1), '0.0');
  assert.equal(context.numOrDash(-0, 1), '0.0');
  assert.equal(context.numOrDash(null, 1), '—');
  assert.equal(context.numOrDash(NaN, 1), '—');
});
