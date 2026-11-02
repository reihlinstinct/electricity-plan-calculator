// Pure calculation core - no DOM, testable in node. Mirrors src/iec_calc/*.
import { TARIFFS } from './tariffs-data.js';

const FRI_SAT = new Set([5, 6]); // JS getDay(): 5=Fri, 6=Sat
export const CITIES = {
  'ירושלים': [31.7683, 35.2137], 'תל אביב': [32.0853, 34.7818], 'חיפה': [32.7940, 34.9896],
  'באר שבע': [31.2529, 34.7915], 'אילת': [29.5577, 34.9519], 'נתניה': [32.3215, 34.8532],
  'חולון': [32.0103, 34.7744], 'פתח תקווה': [32.0871, 34.8878], 'אשדוד': [31.8044, 34.6553],
  'אשקלון': [31.6688, 34.5743], 'ראשון לציון': [31.9730, 34.7925], 'מודיעין': [31.8969, 35.0195],
  'כפר סבא': [32.1750, 34.9069], 'רעננה': [32.1848, 34.8713], 'הרצליה': [32.1624, 34.8447],
  'טבריה': [32.7922, 35.5312], 'צפת': [32.9646, 35.4960], 'עפולה': [32.6078, 35.2897],
  'נצרת': [32.6996, 35.3035], 'עכו': [32.9331, 35.0827], 'כרמיאל': [32.9136, 35.2963],
  'רמת גן': [32.0684, 34.8248], 'בני ברק': [32.0831, 34.8338], 'רחובות': [31.8928, 34.8113],
};

// --- CSV parsing (IEC export: metadata header, then interval rows) ---
export function parseCsv(text) {
  const rows = text.split(/\r?\n/);
  const intervals = [];
  let city = null;
  for (const line of rows) {
    const cells = line.split(',').map(c => c.trim().replace(/^"|"$/g, ''));
    if (cells.length === 3 && cells[2] && /^\d{12}$/.test(cells[2]) && cells[1]) {
      const parts = cells[1].trim().split(/\s+/);
      city = parts[parts.length - 1] || null; // last word of the address = city
    }
    if (cells.length >= 6 && /^\d{2}\/\d{2}\/\d{4}$/.test(cells[2]) && /^\d{1,2}:\d{2}$/.test(cells[3])) {
      const [dd, mm, yyyy] = cells[2].split('/').map(Number);
      let [hh, mi] = cells[3].split(':').map(Number);
      const kwh = parseFloat(cells[4]) || 0, feed = parseFloat(cells[5]) || 0;
      const start = new Date(yyyy, mm - 1, dd, hh === 24 ? 0 : hh, hh === 24 ? 0 : mi);
      if (hh === 24) start.setDate(start.getDate() + 1);
      intervals.push({ start, kwh, feed });
    }
  }
  if (!intervals.length) throw new Error('לא נמצאו שורות צריכה בקובץ. ודאו שזה ייצוא צריכה של חברת החשמל.');
  return { intervals, city };
}

// --- analysis ---
export function summarize(intervals) {
  const daily = new Map();
  const hourly = new Array(24).fill(0);
  const hourlyCount = new Array(24).fill(0);
  for (const i of intervals) {
    const key = i.start.toISOString().slice(0, 10);
    daily.set(key, (daily.get(key) || 0) + i.kwh);
    hourly[i.start.getHours()] += i.kwh;
    hourlyCount[i.start.getHours()]++;
  }
  const total = intervals.reduce((s, i) => s + i.kwh, 0);
  const hourlyAvg = hourly.map((v, h) => hourlyCount[h] ? v / hourlyCount[h] : 0);
  return { days: daily.size, total, daily, hourlyAvg };
}

// --- Taoz rate ---
export function taozRate(when, taoz) {
  const m = when.getMonth() + 1;
  const season = Object.entries(taoz.seasons).find(([, s]) => s.months.includes(m));
  if (!season) throw new Error('no taoz season for month ' + m);
  const s = season[1];
  const day = when.getDay();
  const dateStr = when.toISOString().slice(0, 10);
  let peak;
  if (s.peak.days === 'all') peak = true;
  else if (s.peak.days === 'sun-thu') peak = day >= 0 && day <= 4;
  else peak = day >= 0 && day <= 4; // a-h
  const mins = when.getHours() * 60 + when.getMinutes();
  const [sh, sm] = s.peak.start.split(':').map(Number);
  const [eh, em] = s.peak.end.split(':').map(Number);
  peak = peak && mins >= sh * 60 + sm && mins < eh * 60 + em;
  if (peak && season[0] !== 'winter' &&
      ((taoz.holidays || []).includes(dateStr) || (taoz.holiday_eves || []).includes(dateStr))) peak = false;
  return peak ? s.peak.rate : s.off_peak.rate;
}

// --- plan costs ---
export function planApplies(plan, when) {
  const w = plan.window;
  if (!w) return true;
  const day = when.getDay();
  if (w.days === 'sun-thu' && !(day >= 0 && day <= 4)) return false;
  if (w.days === 'fri-sat' && !(day === 5 || day === 6)) return false;
  const [sh, sm] = w.start.split(':').map(Number);
  const [eh, em] = w.end.split(':').map(Number);
  const start = sh * 60 + sm, end = eh * 60 + em, mins = when.getHours() * 60 + when.getMinutes();
  if (start === end) return true; // all day
  if (start < end) return mins >= start && mins < end;
  return mins >= start || mins < end; // overnight window
}

export function rankPlans(intervals, opts = {}) {
  const flat = TARIFFS.regulated.flat_rate_per_kwh;
  const phase = opts.phase || 'single';
  const vat = TARIFFS.vat_included ? 1.18 : 1.18;
  const iecFixed = (TARIFFS.regulated.fixed_fees_monthly_pre_vat[phase === 'three' ? 'three_phase' : 'single_phase'].total) * 12 * vat;
  const taozFixed = TARIFFS.taoz.fixed_fee_monthly_pre_vat.total * 12 * vat;
  const days = summarize(intervals).days;
  const ann = c => c / days * 365;
  const out = [];
  const flatEnergy = intervals.reduce((s, i) => s + i.kwh * flat, 0);
  const flatAnnual = ann(flatEnergy) + iecFixed;
  out.push({ label: 'חברת החשמל - תעריף אחיד מפוקח', kind: 'flat', annual: flatAnnual, saving: 0 });
  const taozEnergy = intervals.reduce((s, i) => s + i.kwh * taozRate(i.start, TARIFFS.taoz), 0);
  const taozAnnual = ann(taozEnergy) + taozFixed;
  out.push({ label: 'תעו"ז מפוקח (מונה חכם)', kind: 'taoz', annual: taozAnnual, saving: flatAnnual - taozAnnual });
  for (const p of TARIFFS.supplier_plans) {
    if (p.meter === 'smart' && opts.smartMeter === false) continue;
    if (p.requires_gas_customer && opts.gasCustomer === false) continue;
    if (p.requires_hot_customer && opts.hotCustomer === false) continue;
    const cost = intervals.reduce((s, i) => s + i.kwh * flat * (planApplies(p, i.start) ? 1 - p.discount : 1), 0);
    const annual = ann(cost) + iecFixed;
    out.push({ label: `${p.supplier} - ${p.plan}`, kind: 'supplier', annual, saving: flatAnnual - annual, plan: p });
  }
  out.sort((a, b) => a.annual - b.annual);
  return out;
}

// --- weather ---
export function ols(rows, y) {
  const n = rows[0].length;
  const amat = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => rows.reduce((s, r) => s + r[i] * r[j], 0)));
  const bvec = Array.from({ length: n }, (_, i) => rows.reduce((s, r, k) => s + r[i] * y[k], 0));
  for (let i = 0; i < n; i++) {
    let pr = i;
    for (let r = i + 1; r < n; r++) if (Math.abs(amat[r][i]) > Math.abs(amat[pr][i])) pr = r;
    if (Math.abs(amat[pr][i]) < 1e-12) throw new Error('singular design matrix');
    [amat[i], amat[pr]] = [amat[pr], amat[i]];
    [bvec[i], bvec[pr]] = [bvec[pr], bvec[i]];
    const piv = amat[i][i];
    for (let j = i; j < n; j++) amat[i][j] /= piv;
    bvec[i] /= piv;
    for (let k = 0; k < n; k++) if (k !== i) {
      const f = amat[k][i];
      for (let j = i; j < n; j++) amat[k][j] -= f * amat[i][j];
      bvec[k] -= f * bvec[i];
    }
  }
  const mean = y.reduce((a, b) => a + b, 0) / y.length;
  const ssTot = y.reduce((s, v) => s + (v - mean) ** 2, 0);
  const ssRes = rows.reduce((s, r, k) => s + (y[k] - r.reduce((a, x, j) => a + bvec[j] * x, 0)) ** 2, 0);
  return { coef: bvec, r2: ssTot ? 1 - ssRes / ssTot : 0 };
}

export function pstdev(xs) {
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / xs.length);
}

export function hvacSplit(dailyKwh, temps, coolingBase = 22, heatingBase = 18) {
  const days = Object.keys(dailyKwh).filter(d => temps[d] !== undefined).sort();
  if (days.length < 7) return null;
  const cdd = days.map(d => Math.max(0, temps[d] - coolingBase));
  const hdd = days.map(d => Math.max(0, heatingBase - temps[d]));
  if (pstdev(cdd) < 0.2 && pstdev(hdd) < 0.2) return null;
  const rows = days.map((d, i) => [1, [5, 6].includes(new Date(d).getDay()) ? 1 : 0, cdd[i], hdd[i]]);
  const y = days.map(d => dailyKwh[d]);
  const { coef: [b0, bW, bC, bH], r2 } = ols(rows, y);
  const byMonth = {};
  days.forEach((d, i) => {
    const m = d.slice(0, 7);
    byMonth[m] = byMonth[m] || { month: m, days: 0, total: 0, base: 0, weekend: 0, cooling: 0, heating: 0 };
    const o = byMonth[m];
    o.days++; o.total += y[i]; o.base += b0;
    o.weekend += rows[i][1] ? bW : 0; o.cooling += bC * cdd[i]; o.heating += bH * hdd[i];
  });
  return { days: days.length, kwhPerCoolingDegree: bC, kwhPerHeatingDegree: bH, r2,
           coolingBase, heatingBase, monthly: Object.values(byMonth) };
}

export function weatherSensitivity(dailyKwh, temps) {
  const days = Object.keys(dailyKwh).filter(d => temps[d] !== undefined).sort();
  if (days.length < 7) return null;
  const ts = days.map(d => temps[d]);
  if (pstdev(ts) < 1.0) return null;
  const rows = days.map(d => [1, [5, 6].includes(new Date(d).getDay()) ? 1 : 0, temps[d]]);
  const y = days.map(d => dailyKwh[d]);
  const { coef: [, bW, bT], r2 } = ols(rows, y);
  return { days: days.length, kwhPerDegree: bT, weekendExtra: bW, r2,
           tempMin: Math.min(...ts), tempMax: Math.max(...ts) };
}
