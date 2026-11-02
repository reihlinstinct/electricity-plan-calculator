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
  check('footer: links only, no prefix', html.includes('<a href="https://github.com/reihlinstinct/electricity-plan-calculator">GitHub</a> · <a href="sources.html">Sources</a>') && !html.includes('קוד מקור פתוח'));
  check('footer: no bare URL shown', !html.includes('>github.com/reihlinstinct'));
  const src = readFileSync(join(root, 'web', 'sources.html'), 'utf-8');
  check('sources: tariff source links', src.includes('gov.il/BlobFolder') && src.includes('shtipser.com/plans/'));
  check('sources: benchmark links', src.includes('fridges-and-freezers_en') && src.includes('washing-machines_en')
    && src.includes('itu.edu.tr') && src.includes('kfupm.edu.sa') && src.includes('springer.com'));
  check('sources: RTL static, no external loads', src.includes('dir="rtl"') && !src.includes('<script src=') && !src.includes('@import'));
  check('sources: access date recorded', src.includes('2026-11-02'));
  const appJs = readFileSync(join(root, 'web', 'app.js'), 'utf-8');
  check('app: base label is רצפת צריכה', appJs.includes('רצפת צריכה (בסיס):') && !appJs.includes('עומס בסיס לילי'));
  check('app: efficiency renderer', appJs.includes('renderEfficiency'));
  const extRefs = html.match(/(?:src|href)="https?:\/\/[^"]+"/g) || [];
  check('zero external requests: only the repo link is external', extRefs.length === 1 && extRefs[0].includes('github.com/reihlinstinct/electricity-plan-calculator'));
  // CSV export guide (issue #32): web page + images + link from the upload box
  check('guide: linked near upload', html.includes('<a href="guide.html">'));
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

process.exit(failures ? 1 : 0);
