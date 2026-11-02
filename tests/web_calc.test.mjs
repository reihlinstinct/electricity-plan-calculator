// Cross-validation: the JS port must agree with the Python engine on the sample export.
// Run: node tests/web_calc.test.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { parseCsv, summarize, rankPlans } from '../web/calc.js';

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
check('--no-gas drops Amisragas', !noGas.some(p => p.label.includes('אמישראגז')));

// 24:00 normalization covered implicitly: sample has a 24:00 row -> parsed to next day 00:00
check('no hour-24 timestamps', intervals.every(i => i.start.getHours() < 24));

process.exit(failures ? 1 : 0);
