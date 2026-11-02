// Cross-validation: the JS port must agree with the Python engine on the sample export.
// Run: node tests/web_calc.test.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { intervalHours, parseCsv, summarize, rankPlans, detectAppliances, buildInsights, sunsetLocalMinutes } from '../web/calc.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const text = readFileSync(join(root, 'data', 'sample_consumption.csv'), 'utf-8');

let failures = 0;
function check(name, cond) {
  if (!cond) { failures++; console.error('FAIL', name); } else console.log('ok', name);
}

const intervals = parseCsv(text);
check('1344 intervals parsed', intervals.length === 1344);
const sum = summarize(intervals);
check('14 local days (no UTC phantom day)', sum.days === 14);

const ranked = rankPlans(intervals, {});
check('20 plans ranked by default (gas/HOT excluded)', ranked.length === 20);
check('default excludes Amisragas', !ranked.some(p => p.label.includes('אמישראגז')));
const rankedAll = rankPlans(intervals, { gasCustomer: true, hotCustomer: true });
check('22 plans with opt-ins', rankedAll.length === 22);
check('sorted ascending', ranked.every((p, i) => i === 0 || ranked[i - 1].annual <= p.annual));
// expected values from the Python engine on the same file
check('taoz annual = 3185', Math.round(ranked.find(p => p.kind === 'taoz').annual) === 3185);
check('flat annual = 3774', Math.round(ranked.find(p => p.kind === 'flat').annual) === 3774);
check('best is taoz on the sample', ranked[0].kind === 'taoz');

// eligibility flags
const noGas = rankPlans(intervals, { gasCustomer: false });
check('gas plan excluded by default', !noGas.some(p => p.label.includes('אמישראגז')));

// 24:00 normalization covered implicitly: sample has a 24:00 row -> parsed to next day 00:00
check('no hour-24 timestamps', intervals.every(i => i.start.getHours() < 24));

// --- insights ---
function flatDay(d, baseKw = 0.2) {
  const out = [];
  for (let h = 0; h < 24; h++) for (const m of [0, 15, 30, 45])
    out.push({ start: new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, m), kwh: baseKw * 0.25, feed: 0 });
  return out;
}
function setBlock(ivs, startIdx, kws) {
  kws.forEach((kw, i) => { ivs[startIdx + i] = { start: ivs[startIdx + i].start, kwh: kw * 0.25, feed: 0 }; });
}
{
  const ivs = flatDay(new Date(2026, 9, 5)); // Monday
  setBlock(ivs, 10 * 4, [0.4, 0.4, 0.4, 2.0, 2.0, 0.4, 0.4, 0.6]); // washer shape
  const ev = detectAppliances(ivs, 0.2);
  check('js: washer detected high', ev.length === 1 && ev[0].kind === 'washing_machine' && ev[0].confidence === 'high');
  check('js: event end is end of last interval', ev[0].end - ev[0].start === 8 * 900 * 1000); // 10:00-12:00
  check('js: intervalHours from data median', intervalHours(ivs) === 0.25);
  const hourly = ivs.filter((_, i) => i % 4 === 0);
  check('js: intervalHours hourly median', intervalHours(hourly) === 1);
}
{
  const ivs = flatDay(new Date(2026, 9, 6));
  setBlock(ivs, 18 * 4, [2.2, 0.3, 2.2, 0.3, 2.2, 0.3, 2.2, 0.3]); // thermostat cycling
  const ev = detectAppliances(ivs, 0.2);
  check('js: oven detected medium', ev.length === 1 && ev[0].kind === 'oven');
}
{
  const ivs = flatDay(new Date(2026, 9, 7));
  setBlock(ivs, 19 * 4, [1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2]); // 2h steady
  const ev = detectAppliances(ivs, 0.2);
  check('js: sustained high, type unclear', ev.length === 1 && ev[0].kind === 'sustained_high' && ev[0].confidence === 'low');
}
{
  const ivs = flatDay(new Date(2026, 9, 9));
  setBlock(ivs, 7 * 4, Array(64).fill(1.0)); // 16h block: not an appliance
  check('js: daylong block ignored', detectAppliances(ivs, 0.2).length === 0);
}
{
  const ivs = parseCsv(text);
  const ins = buildInsights(ivs);
  check('js: insights coverage flag', ins.coversFullYear === false && ins.days === 14);
  check('js: insights night base positive', ins.nightBaseKw > 0.1 && ins.nightBaseKw < 0.5);
  check('js: insights taoz peak share sane', ins.taozPeakCostShare > 0 && ins.taozPeakCostShare < 1);
  check('js: insights peak hours top=21', ins.peakHours[0][0] === 21);
  check('js: peak hours per hour, CLI units', Math.abs(ins.peakHours[0][1] - 1.219) < 0.01);
}

{
  // Shabbat-aware split: raised Friday/Saturday baseline must not pollute the weekday base
  const ivs = [];
  for (let i = 0; i < 14; i++) {
    const d = new Date(2026, 9, 5 + i);
    ivs.push(...flatDay(d, d.getDay() === 6 ? 0.45 : 0.2));
  }
  const ins = buildInsights(ivs);
  check('js: shabbat split - weekday base low', ins.nightBaseKw < 0.25);
  check('js: shabbat split - shabbat base high', ins.shabbatNightBaseKw > 0.4);
  check('js: shabbat windows counted', ins.shabbatCount >= 1);
  check('js: no appliance false positive from plate/urn', ins.appliances.length === 0);
}
{
  // Shabbat-observance detection parity with the Python engine (issue #38)
  const household = (days, shabbatNightKw, weekdayWashers, shabbatWashers) => {
    const out = [];
    for (let i = 0; i < days; i++) {
      const d = new Date(2026, 9, 7 + i); // starts Wednesday
      const day = flatDay(d, 0.2);
      if (d.getDay() === 6) for (let h = 2; h < 5; h++) setBlock(day, h * 4, [shabbatNightKw, shabbatNightKw, shabbatNightKw, shabbatNightKw]);
      if (weekdayWashers.includes(i) || shabbatWashers.includes(i))
        setBlock(day, 10 * 4, [0.4, 0.4, 0.4, 2.0, 2.0, 0.4, 0.4, 0.6]);
      out.push(...day);
    }
    return out;
  };
  let ins = buildInsights(household(21, 0.5, [0, 1, 4, 6, 8, 12], []));
  check('js: observance high on both signals', ins.observance && ins.observance.confidence === 'high'
    && ins.observance.signals.includes('base') && ins.observance.signals.includes('appliances'));
  ins = buildInsights(household(21, 0.2, [1, 8, 15], [3, 10])); // flat nights, washers on Shabbat too
  check('js: observance neutral for non-observant', ins.observance === null);
  ins = buildInsights(household(6, 0.5, [1, 3], [])); // too little data
  check('js: observance neutral with 1 Shabbat', ins.observance === null);
}
{
  // efficiency notes parity (issue #40): floor + washer on the synthetic observant household
  const household = (days, shabbatNightKw, weekdayWashers) => {
    const out = [];
    for (let i = 0; i < days; i++) {
      const d = new Date(2026, 9, 7 + i);
      const day = flatDay(d, 0.2);
      if (d.getDay() === 6) for (let h = 2; h < 5; h++) setBlock(day, h * 4, [shabbatNightKw, shabbatNightKw, shabbatNightKw, shabbatNightKw]);
      if (weekdayWashers.includes(i)) setBlock(day, 10 * 4, [0.4, 0.4, 0.4, 2.0, 2.0, 0.4, 0.4, 0.6]);
      out.push(...day);
    }
    return out;
  };
  const ins = buildInsights(household(21, 0.5, [0, 1, 4, 6, 8, 12]));
  const kinds = ins.efficiency.map(n => n.kind);
  check('js: floor note fires', kinds.includes('floor'));
  check('js: washer note fires with eco caveat', kinds.includes('washer')
    && ins.efficiency.find(n => n.kind === 'washer').text.includes('ממוצע 2024')
    && ins.efficiency.find(n => n.kind === 'washer').text.includes('לא פסיקה'));
  const quiet = [];
  for (let i = 0; i < 10; i++) quiet.push(...flatDay(new Date(2026, 9, 5 + i), 0.1));
  check('js: quiet household no efficiency notes', buildInsights(quiet).efficiency.length === 0);
}
{
  const m = sunsetLocalMinutes(new Date(2026, 9, 15), 31.78, 35.21) / 60;
  check('js: sunset Jerusalem Oct ~18.1h', m > 17.8 && m < 18.5);
}

// --- share preview + favicon (issue #26): tags present, absolute URLs, assets on disk ---
{
  const html = readFileSync(join(root, 'web', 'index.html'), 'utf-8');
  const BASE = 'https://reihlinstinct.github.io/electricity-plan-calculator/web/';
  check('meta: og:title', html.includes('property="og:title"'));
  check('meta: og:description', html.includes('property="og:description"'));
  check('meta: og:locale he_IL', html.includes('property="og:locale" content="he_IL"'));
  check('meta: og:image absolute', html.includes(`property="og:image" content="${BASE}og-image.png"`));
  check('meta: twitter card', html.includes('name="twitter:card" content="summary_large_image"'));
  check('meta: twitter image absolute', html.includes(`name="twitter:image" content="${BASE}og-image.png"`));
  check('icon: favicon link', html.includes('rel="icon"') && html.includes('favicon.png'));
  check('icon: apple-touch-icon link', html.includes('rel="apple-touch-icon"'));

  // repo footer link (issue #28): plain <a>, and it is the ONLY external URL reference
  check('footer: links only, no prefix', html.includes('<a href="https://github.com/reihlinstinct/electricity-plan-calculator" data-i18n="ui.footer_github">GitHub</a> · <a href="sources.html" data-i18n="ui.footer_sources">Sources</a>') && !html.includes('קוד מקור פתוח'));
  check('footer: no bare URL shown', !html.includes('>github.com/reihlinstinct'));
  const src = readFileSync(join(root, 'web', 'sources.html'), 'utf-8');
  check('sources: tariff source links', src.includes('gov.il/BlobFolder') && src.includes('shtipser.com/plans/'));
  check('sources: benchmark links', src.includes('fridges-and-freezers_en') && src.includes('washing-machines_en')
    && src.includes('itu.edu.tr') && src.includes('kfupm.edu.sa') && src.includes('springer.com'));
  check('sources: RTL static, no external loads', src.includes('dir="rtl"') && !src.includes('<script src=') && !src.includes('@import'));
  check('sources: access date recorded', src.includes('2026-11-02'));
  const appJs = readFileSync(join(root, 'web', 'app.js'), 'utf-8');
  const i18nData = readFileSync(join(root, 'web', 'i18n-data.js'), 'utf-8');
  check('app: base label is רצפת צריכה', i18nData.includes('רצפת צריכה (בסיס):') && !i18nData.includes('עומס בסיס לילי'));
  check('app: efficiency renderer', appJs.includes('renderEfficiency'));
  const extRefs = html.match(/(?:src|href)="https?:\/\/[^"]+"/g) || [];
  check('zero external requests: only the repo link is external', extRefs.length === 1 && extRefs[0].includes('github.com/reihlinstinct/electricity-plan-calculator'));
  // CSV export guide (issue #32): web page + images + link from the upload box
  check('guide: linked near upload', html.includes('<a href="guide.html" data-i18n="ui.guide_link">'));
  const guide = readFileSync(join(root, 'web', 'guide.html'), 'utf-8');
  check('guide: rtl hebrew page', guide.includes('dir="rtl"') && guide.includes('lang="he"'));
  const guideImgs = [...guide.matchAll(/<img src="([^"]+)"/g)].map(m => m[1]);
  check('guide: six step images', guideImgs.length === 6);
  check('guide: images exist and are local', guideImgs.every(p => {
    if (p.startsWith('http')) return false;
    try { readFileSync(join(root, 'web', p)); return true; } catch { return false; }
  }));
  check('guide: no external resource loads', !(guide.match(/src="https?:/) || guide.match(/<link[^>]+href="https?:/)));

  const pngSize = path => {
    const b = readFileSync(path);
    check(`${path} is a PNG`, b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47);
    return [b.readUInt32BE(16), b.readUInt32BE(20)];
  };
  const [ow, oh] = pngSize(join(root, 'web', 'og-image.png'));
  check('og:image is 1200x630', ow === 1200 && oh === 630);
  const [aw, ah] = pngSize(join(root, 'web', 'apple-touch-icon.png'));
  check('apple-touch-icon is 180x180', aw === 180 && ah === 180);
  const [fw, fh] = pngSize(join(root, 'web', 'favicon.png'));
  check('favicon is square and small', fw === fh && fw <= 64);
}


// --- i18n (issue #44): every data-i18n key exists in the bundled strings, placeholders substitute ---
{
  const { t } = await import('../web/i18n.js');
  check('i18n: t substitutes', t('app.days_measured', { days: 3 }, 'he') === '3 ימי מדידה');
  check('i18n: unknown key returns key', t('no.such.key', {}, 'he') === 'no.such.key');
  const { I18N } = await import('../web/i18n-data.js');
  let missing = [];
  for (const page of ['index.html', 'guide.html', 'sources.html']) {
    const body = readFileSync(join(root, 'web', page), 'utf-8');
    for (const m of body.match(/data-i18n(?:-title)?="[^"]+"/g) || []) {
      const key = m.replace(/^data-i18n(?:-title)?="/, '').replace(/"$/, '');
      if (!I18N.strings[key]) missing.push(`${page}:${key}`);
    }
  }
  check('i18n: all page keys exist in strings', missing.length === 0);
  check('i18n: he is default rtl', I18N.languages.he && I18N.languages.he.default && I18N.languages.he.dir === 'rtl');
  check('i18n: en present ltr, not default', I18N.languages.en && I18N.languages.en.dir === 'ltr' && !I18N.languages.en.default);
  check('i18n: en translation renders', t('ui.title', {}, 'en') === 'Electricity plan calculator');
  check('i18n: og keys exist in both languages', ['he', 'en'].every(l => I18N.strings['ui.og_title'][l] && I18N.strings['ui.og_desc'][l]));
  check('i18n: unknown language falls back to he', t('ui.title', {}, 'fr') === t('ui.title', {}, 'he'));
  // selector redesign (issue #54): a native select inside the header on every page,
  // flex space-between puts it opposite the title in both directions
  for (const page of ['index.html', 'guide.html', 'sources.html']) {
    const body = readFileSync(join(root, 'web', page), 'utf-8');
    check(`${page}: select#langSwitch inside header`, /<header><select id="langSwitch"><\/select><h1/.test(body));
    check(`${page}: header flex opposite-side`, /header \{[^}]*display:flex[^}]*justify-content:space-between[^}]*flex-direction:row-reverse/s.test(body));
    check(`${page}: no old nav bar`, !body.includes('<nav id="langSwitch"'));
  }
  check('i18n: footer sources label localized', I18N.strings['ui.footer_sources'].he === 'מקורות' && I18N.strings['ui.footer_sources'].en === 'Sources');
  check('i18n: selector aria-label key in all languages', ['he', 'en'].every(l => I18N.strings['ui.lang_switch_label'][l]));
  check('i18n: option labels are 2-letter codes', Object.keys(I18N.languages).every(c => c.length === 2 && c.toUpperCase().length === 2));
  // issue #56: no hostname-list box on the main page; sources live only on the Sources page
  {
    const idx = readFileSync(join(root, 'web', 'index.html'), 'utf-8');
    check('index: no tariff-sources box', !idx.includes('ui.tariff_sources') && !idx.includes('id="sources"'));
    const appJs = readFileSync(join(root, 'web', 'app.js'), 'utf-8');
    check('index: app.js does not fill a sources list', !appJs.includes("$('sources')"));
    const srcPage = readFileSync(join(root, 'web', 'sources.html'), 'utf-8');
    check('sources page lists all tariff hosts', ['gov.il', 'chashmali.com', 'shtipser.com', 'kolhabait.com', 'hebcal.com'].every(h => srcPage.includes(h)));
  }
}

// --- link hygiene (issue #45): repo/source links point at main, hosts are expected, internal links exist ---
import { existsSync, readdirSync } from 'node:fs';
const ALLOWED_HOSTS = new Set([
  'github.com', 'www.gov.il', 'chashmali.com', 'shtipser.com', 'kolhabait.com', 'www.hebcal.com', 'www.iec.co.il', 'reihlinstinct.github.io',
  'www.ynet.co.il', 'energy-efficient-products.ec.europa.eu', 'research.itu.edu.tr',
  'pure.kfupm.edu.sa', 'link.springer.com',
]);
const pagesAndDocs = ['web/index.html', 'web/guide.html', 'web/sources.html', 'README.md', 'DESIGN.md',
  ...readdirSync(join(root, 'docs')).filter(f => f.endsWith('.md')).map(f => join('docs', f))];
let linkFails = 0;
for (const rel of pagesAndDocs) {
  const body = readFileSync(join(root, rel), 'utf-8');
  if (/design-doc|\/tree\/|\/blob\//.test(body)) { console.error('FAIL branch ref in', rel); linkFails++; }
  for (const m of body.match(/https?:\/\/[^"'\s)>]+/g) || []) {
    const host = m.replace(/^https?:\/\//, '').split('/')[0];
    if (!m.startsWith('https://') || !ALLOWED_HOSTS.has(host)) { console.error('FAIL unexpected link', rel, m); linkFails++; }
  }
  if (rel.startsWith('web/')) {
    for (const m of body.match(/(?:href|src)="(?!https?:|#|mailto:|data:)[^"]+"/g) || []) {
      const target = m.replace(/^(?:href|src)="/, '').replace(/"$/, '').split('#')[0].split('?')[0];
      if (target && !existsSync(join(root, 'web', target))) { console.error('FAIL broken internal link', rel, target); linkFails++; }
    }
  }
}
check('links: no branch refs, expected hosts only, internal links resolve (issue #45)', linkFails === 0);


// --- functional: full language switch after a calculation leaves no stale strings (#54 review) ---
{
  const allEls = new Set();
  const mkEl = (tag = 'div') => {
    const e = {
      tag, children: [], textContent: '', value: '', style: {}, attrs: {}, listeners: {},
      selectedIndex: 0, files: [], checked: false, disabled: false, width: 300, height: 150,
      className: '', innerHTML: '', dataset: {},
      appendChild(c) { this.children.push(c); c.parent = this; return c; },
      append(...cs) { for (const c of cs) this.appendChild(typeof c === 'string' ? { textContent: c, children: [] } : c); },
      replaceChildren(...cs) {
        const detach = c => { c.detached = true; (c.children || []).forEach(detach); };
        this.children.forEach(detach);
        this.children = [...cs];
        this.children.forEach(c => { c.parent = this; c.detached = false; });
      },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return this.attrs[k] ?? null; },
      hasAttribute(k) { return k in this.attrs; },
      addEventListener(ev, fn) { this.listeners[ev] = fn; },
      dispatchEvent(ev) { this.listeners[ev.type]?.(ev); },
      insertRow() { const r = mkEl('tr'); this.children.push(r); r.parent = this; return r; },
      insertCell() { const c = mkEl('td'); this.children.push(c); c.parent = this; return c; },
      querySelector(sel) {
        const m = sel.match(/^option\[value="([^"]*)"\]$/);
        return m ? this.children.find(c => c.value === m[1]) ?? null : null;
      },
      getContext() { return new Proxy({}, { get: (t, k) => () => {}, set: () => true }); },
      get options() { return this.children; },
    };
    Object.defineProperty(e, 'innerHTML', {
      get() { return this._innerHTML || ''; },
      set(v) { this._innerHTML = v; if (v === '') this.replaceChildren(); },
    });
    const tc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e), 'textContent');
    allEls.add(e);
    return e;
  };
  const byId = {};
  const staticEls = [];
  {
    const html = readFileSync(join(root, 'web', 'index.html'), 'utf-8');
    for (const m of html.match(/data-i18n(?:-alt|-title)?="[^"]+"/g) || []) {
      const [attr, key] = m.split('="');
      staticEls.push(Object.assign(mkEl('span'), { attrs: { [attr]: key.replace(/"$/, '') } }));
    }
  }
  const docListeners = {};
  const documentStub = {
    title: '', documentElement: mkEl('html'),
    getElementById(id) {
      const tag = id === 'currentPlan' || id === 'langSwitch' || id === 'phase' ? 'select'
        : id.startsWith('ch') ? 'canvas' : 'div';
      return byId[id] ??= mkEl(tag);
    },
    createElement: tag => mkEl(tag),
    createTextNode: txt => ({ textContent: txt, children: [] }),
    querySelector: () => null,
    querySelectorAll(sel) {
      if (sel === '[data-i18n]') return staticEls.filter(e => 'data-i18n' in e.attrs);
      if (sel === '[data-i18n-title]') return staticEls.filter(e => 'data-i18n-title' in e.attrs);
      return [];
    },
    addEventListener(ev, fn) { docListeners[ev] = fn; },
    dispatchEvent(ev) { docListeners[ev.type]?.(ev); },
  };
  class CustomEventStub { constructor(type) { this.type = type; } }
  const windowStub = {
    location: { search: '?lang=he', pathname: '/web/' },
    history: { replaceState(s, t, u) { windowStub.location.search = u.includes('?') ? u.slice(u.indexOf('?')) : ''; } },
    URLSearchParams, CustomEvent: CustomEventStub,
  };
  globalThis.document = documentStub;
  globalThis.window = windowStub;
  globalThis.location = windowStub.location;
  globalThis.CustomEvent = CustomEventStub;

  // placeholder option like the real markup
  const planSel = documentStub.getElementById('currentPlan');
  const ph = mkEl('option'); ph.value = ''; ph.textContent = '-';
  planSel.appendChild(ph);
  planSel.selectedIndex = 0;
  documentStub.getElementById('phase').value = 'single';
  documentStub.getElementById('csv').files = [{ text: async () => text }];
  documentStub.getElementById('smartMeter').checked = true;

  await import('../web/app.js');
  const collect = () => {
    const out = [];
    const walk = e => { if (e.textContent) out.push(e.textContent); (e.children || []).forEach(walk); };
    allEls.forEach(e => { if (!e.parent && !e.detached) walk(e); });
    return out;
  };

  await byId.go.listeners.click();
  let texts = collect().join('\n');
  check('langswitch: he render has Hebrew plan label + column', texts.includes('חברת החשמל - תעריף אחיד מפוקח') && texts.includes('עלות שנתית'));

  const switchTo = code => { byId.langSwitch.value = code; byId.langSwitch.listeners.change(); };
  switchTo('en');
  texts = collect().join('\n');
  check('langswitch: url updated', windowStub.location.search === '?lang=en');
  check('langswitch: en render has English plan label + column', texts.includes('Israel Electric Corp - regulated flat rate') && texts.includes('Annual cost'));
  const staleHe = ['עלות שנתית', 'חברת החשמל - תעריף אחיד מפוקח', 'ימי מדידה', 'הכי משתלם', 'תובנות מהנתונים']
    .filter(s => texts.includes(s));

  check('langswitch: no stale Hebrew UI strings after switch', staleHe.length === 0);
  check('langswitch: plan select repopulated in en', byId.currentPlan.children.some(o => o.value === 'Israel Electric Corp - regulated flat rate'));

  switchTo('he');
  texts = collect().join('\n');
  check('langswitch: back to he, no stale English UI strings', !texts.includes('Annual cost') && texts.includes('עלות שנתית'));
}

// --- CSS contract: 360px no-overflow guards (#54 review) ---
{
  const idx = readFileSync(join(root, 'web', 'index.html'), 'utf-8');
  check('index: opts row exists', idx.includes('class="opts"'));
  check('css: .opts label may shrink (min-width:0)', /\.opts label \{[^}]*min-width:0/.test(idx));
  check('css: .opts select fills its label (width:100%)', /\.opts select \{[^}]*width:100%/.test(idx));
  for (const page of ['index.html', 'guide.html', 'sources.html']) {
    const body = readFileSync(join(root, 'web', page), 'utf-8');
    check(`css: ${page} global select max-width guard`, /select \{ max-width:100%/.test(body));
  }
}

process.exit(failures ? 1 : 0);
