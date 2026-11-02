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

process.exit(failures ? 1 : 0);
