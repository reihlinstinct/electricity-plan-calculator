// Pure calculation core - no DOM, testable in node. Mirrors src/iec_calc/*.
import { TARIFFS, BENCHMARKS } from './tariffs-data.js';
import { t } from './i18n.js';

const FRI_SAT = new Set([5, 6]); // JS getDay(): 5=Fri, 6=Sat

export function dateKey(d) {
  // local date (never toISOString: UTC conversion shifts days around midnight)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// --- CSV parsing (IEC export: metadata header, then interval rows) ---
export function parseCsv(text) {
  const rows = text.split(/\r?\n/);
  const intervals = [];
  for (const line of rows) {
    const cells = line.split(',').map(c => c.trim().replace(/^"|"$/g, ''));
    if (cells.length >= 6 && /^\d{2}\/\d{2}\/\d{4}$/.test(cells[2]) && /^\d{1,2}:\d{2}$/.test(cells[3])) {
      const [dd, mm, yyyy] = cells[2].split('/').map(Number);
      let [hh, mi] = cells[3].split(':').map(Number);
      // 24:00 is the only valid next-day spelling; Date would otherwise
      // silently normalize 24:30, 25:00 or 12:60 into a different interval.
      if (!((hh >= 0 && hh < 24 && mi >= 0 && mi < 60) || (hh === 24 && mi === 0))) continue;
      const kwh = parseFloat(cells[4]) || 0, feed = parseFloat(cells[5]) || 0;
      const start = new Date(yyyy, mm - 1, dd, hh === 24 ? 0 : hh, hh === 24 ? 0 : mi);
      if (hh === 24) start.setDate(start.getDate() + 1);
      intervals.push({ start, kwh, feed });
    }
  }
  if (!intervals.length) throw new Error(t('calc.err_no_rows'));
  return intervals;
}

// --- analysis ---
export function summarize(intervals) {
  const daily = new Map();
  const hourly = new Array(24).fill(0);
  const hourlyCount = new Array(24).fill(0);
  for (const i of intervals) {
    const key = dateKey(i.start);
    daily.set(key, (daily.get(key) || 0) + i.kwh);
    hourly[i.start.getHours()] += i.kwh;
    hourlyCount[i.start.getHours()]++;
  }
  const total = intervals.reduce((s, i) => s + i.kwh, 0);
  const hourlyAvg = hourly.map((v, h) => hourlyCount[h] ? v / hourlyCount[h] : 0);
  return { days: daily.size, total, daily, hourlyAvg };
}

// --- Taoz rate ---
export function taozIsPeak(when, taoz) {
  const m = when.getMonth() + 1;
  const season = Object.entries(taoz.seasons).find(([, s]) => s.months.includes(m));
  if (!season) throw new Error('no taoz season for month ' + m);
  const s = season[1];
  const day = when.getDay();
  const dateStr = dateKey(when);
  let peak;
  if (s.peak.days === 'all') peak = true;
  else peak = day >= 0 && day <= 4; // sun-thu
  const mins = when.getHours() * 60 + when.getMinutes();
  const [sh, sm] = s.peak.start.split(':').map(Number);
  const [eh, em] = s.peak.end.split(':').map(Number);
  peak = peak && mins >= sh * 60 + sm && mins < eh * 60 + em;
  if (peak && season[0] !== 'winter' &&
      ((taoz.holidays || []).includes(dateStr) || (taoz.holiday_eves || []).includes(dateStr))) peak = false;
  return peak;
}

export function taozRate(when, taoz) {
  const m = when.getMonth() + 1;
  const season = Object.entries(taoz.seasons).find(([, s]) => s.months.includes(m));
  if (!season) throw new Error('no taoz season for month ' + m);
  return taozIsPeak(when, taoz) ? season[1].rates.peak : season[1].rates.off_peak;
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
  const vat = 1 + TARIFFS.vat_rate;
  const iecFixed = (TARIFFS.regulated.fixed_fees_monthly_pre_vat[phase === 'three' ? 'three_phase' : 'single_phase'].total) * 12 * vat;
  const taozFixed = TARIFFS.taoz.fixed_fee_monthly_pre_vat.total * 12 * vat;
  const days = summarize(intervals).days;
  const ann = c => c / days * 365;
  const out = [];
  const flatEnergy = intervals.reduce((s, i) => s + i.kwh * flat, 0);
  const flatAnnual = ann(flatEnergy) + iecFixed;
  out.push({ label: t('plan.flat_label'), kind: 'flat', annual: flatAnnual, saving: 0 });
  const taozEnergy = intervals.reduce((s, i) => s + i.kwh * taozRate(i.start, TARIFFS.taoz), 0);
  const taozAnnual = ann(taozEnergy) + taozFixed;
  out.push({ label: t('plan.taoz_label'), kind: 'taoz', annual: taozAnnual, saving: flatAnnual - taozAnnual });
  for (const p of TARIFFS.supplier_plans) {
    if (p.meter === 'smart' && opts.smartMeter === false) continue;
    if (p.requires_gas_customer && opts.gasCustomer !== true) continue;
    if (p.requires_hot_customer && opts.hotCustomer !== true) continue;
    const cost = intervals.reduce((s, i) => s + i.kwh * flat * (planApplies(p, i.start) ? 1 - p.discount : 1), 0);
    const annual = ann(cost) + iecFixed;
    out.push({ label: `${p.supplier} - ${p.plan}`, kind: 'supplier', annual, saving: flatAnnual - annual, plan: p });
  }
  out.sort((a, b) => a.annual - b.annual);
  return out;
}

// --- insights (descriptive, CSV-only; appliances are probabilistic load signatures) ---
const MIN_EXCESS_KW = 0.15, HIGH_KW = 1.2;
const WASHER_MIN = 45, WASHER_MAX = 180, OVEN_MIN = 20, OVEN_MAX = 150;
const SUST_MIN = 45, SUST_MAX = 360, SUST_MIN_MEAN = 0.8;

// Median interval length in hours, from the data itself (mirrors Python _interval_hours).
export function intervalHours(intervals) {
  const deltas = [];
  for (let k = 0; k + 1 < intervals.length; k++) {
    const d = (intervals[k + 1].start - intervals[k].start) / 1000;
    if (d > 0 && d <= 3600) deltas.push(d);
  }
  if (!deltas.length) return 0.25;
  deltas.sort((a, b) => a - b);
  const mid = Math.floor(deltas.length / 2);
  const med = deltas.length % 2 ? deltas[mid] : (deltas[mid - 1] + deltas[mid]) / 2;
  return med / 3600;
}

export function detectAppliances(intervals, baseKw) {
  const hours = intervalHours(intervals);
  const ex = intervals.map(i => i.kwh / hours - baseKw);
  const blocks = [];
  let i = 0;
  while (i < ex.length) {
    if (ex[i] > MIN_EXCESS_KW) {
      let j = i;
      while (j + 1 < ex.length && (ex[j + 1] > MIN_EXCESS_KW || (j + 2 < ex.length && ex[j + 2] > MIN_EXCESS_KW)))
        j += ex[j + 1] > MIN_EXCESS_KW ? 1 : 2;
      blocks.push([i, j]);
      i = j + 1;
    } else i++;
  }
  const events = [];
  for (const [a, b] of blocks) {
    const exs = ex.slice(a, b + 1);
    const durMin = exs.length * hours * 60;
    const energy = exs.reduce((s, e) => s + e * hours, 0);
    const start = intervals[a].start;
    const end = new Date(intervals[b].start.getTime() + hours * 3600e3); // end of last interval, not its start
    let run = 0, maxConsecHi = 0;
    for (const e of exs) { run = e >= HIGH_KW ? run + 1 : 0; maxConsecHi = Math.max(maxConsecHi, run); }
    let transitions = 0;
    for (let k = 0; k + 1 < exs.length; k++)
      if ((exs[k] >= HIGH_KW) !== (exs[k + 1] >= HIGH_KW) && Math.min(exs[k], exs[k + 1]) < 0.6) transitions++;
    const maxEx = Math.max(...exs), meanEx = exs.reduce((s, e) => s + e, 0) / exs.length;
    if (durMin >= WASHER_MIN && durMin <= WASHER_MAX && maxConsecHi >= 2 &&
        exs.filter(e => e > MIN_EXCESS_KW && e < HIGH_KW).length >= 3 && energy >= 0.4 && energy <= 2.5) {
      events.push({ kind: 'washing_machine', confidence: maxEx >= 1.5 && energy >= 0.6 ? 'high' : 'medium',
        start, end, excessKwh: Math.round(energy * 100) / 100,
        pattern: t('calc.pattern_washer', { dur: Math.round(durMin), consec: maxConsecHi, max: maxEx.toFixed(1) }) });
    } else if (durMin >= OVEN_MIN && durMin <= OVEN_MAX && maxEx >= 1.5 && transitions >= 3) {
      events.push({ kind: 'oven', confidence: 'medium', start, end, excessKwh: Math.round(energy * 100) / 100,
        pattern: t('calc.pattern_oven', { dur: Math.round(durMin), transitions, max: maxEx.toFixed(1) }) });
    } else if (durMin >= SUST_MIN && durMin <= SUST_MAX && meanEx >= SUST_MIN_MEAN) {
      events.push({ kind: 'sustained_high', confidence: 'low', start, end, excessKwh: Math.round(energy * 100) / 100,
        pattern: t('calc.pattern_sustained', { mean: meanEx.toFixed(1), dur: Math.round(durMin) }) });
    }
  }
  return events;
}

// NOAA solar approximation, local clock minutes (Israeli DST aware). No network.
function israelUtcOffset(d) {
  // Last Sunday of a month: day 0 of month m+1 is the last day of month m (m 0-based).
  const lastSunday = m => {
    let x = new Date(d.getFullYear(), m + 1, 0);
    while (x.getDay() !== 0) x = new Date(x.getFullYear(), x.getMonth(), x.getDate() - 1);
    return x;
  };
  const end = lastSunday(9); // October: DST ends
  const ls3 = lastSunday(2); // March: DST starts the Friday before
  const start = new Date(ls3.getFullYear(), ls3.getMonth(), ls3.getDate() - 2); // Friday before
  const t = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  return t >= start && t < end ? 3 : 2;
}

export function sunsetLocalMinutes(d, lat, lon) {
  const g = 2 * Math.PI / 365 * (Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 864e5) - 1);
  const eqtime = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
    + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const latr = lat * Math.PI / 180;
  const cosHa = Math.cos(90.833 * Math.PI / 180) / (Math.cos(latr) * Math.cos(decl)) - Math.tan(latr) * Math.tan(decl);
  const ha = Math.acos(Math.min(1, Math.max(-1, cosHa))) * 180 / Math.PI;
  return 720 - 4 * (lon - ha) - eqtime + 60 * israelUtcOffset(d);
}

export function shabbatWindow(saturday) {
  const sat0 = new Date(saturday.getFullYear(), saturday.getMonth(), saturday.getDate()); // midnight
  const friday = new Date(sat0.getFullYear(), sat0.getMonth(), sat0.getDate() - 1);
  const [lat, lon] = [31.7683, 35.2137];
  const start = new Date(friday.getTime() + sunsetLocalMinutes(friday, lat, lon) * 60000);
  const end = new Date(sat0.getTime() + (sunsetLocalMinutes(sat0, lat, lon) + 42) * 60000);
  return [start, end];
}

// Shabbat-observance detection thresholds (statistics only, never a negative claim).
// Keep in parity with src/iec_calc/insights.py.
const OBS_MIN_SHABBATOT = 2;
const OBS_MIN_WEEKDAYS = 5;
const OBS_BASE_MIN_DELTA_KW = 0.05;
const OBS_BASE_RATIO = 1.3;
const OBS_WEEKDAY_MIN_RATE = 0.15;
const OBS_SHABBAT_MAX_SHARE = 0.25;

export function detectShabbatObservance({ shabbatCount, weekdayDays, nightBaseKw, shabbatNightBaseKw, shabbatStarts, weekdayStarts }) {
  if (shabbatCount < OBS_MIN_SHABBATOT || weekdayDays < OBS_MIN_WEEKDAYS) return null;
  const signals = [];
  const baseRatio = nightBaseKw > 0 ? shabbatNightBaseKw / nightBaseKw : 0;
  if (nightBaseKw > 0 && shabbatNightBaseKw - nightBaseKw >= OBS_BASE_MIN_DELTA_KW && baseRatio >= OBS_BASE_RATIO) signals.push('base');
  const weekdayRate = weekdayStarts / weekdayDays;
  if (weekdayRate >= OBS_WEEKDAY_MIN_RATE && shabbatStarts / shabbatCount <= OBS_SHABBAT_MAX_SHARE * weekdayRate) signals.push('appliances');
  if (!signals.length) return null;
  return { confidence: signals.length === 2 ? 'high' : 'medium', signals, baseRatio, shabbatStarts, shabbatCount, weekdayRate };
}

// Efficiency-note thresholds (context only, never a verdict). Parity: src/iec_calc/insights.py.
const FLOOR_NOTE_KW = 0.15;
const WASHER_NOTE_RATIO = 1.3;
const WASHER_MIN_EVENTS = 2;
const SUSTAINED_MIN_EVENTS = 3;
const SUSTAINED_MIN_MEAN_EXCESS_KW = 1.0;
const UNATTENDED_START_HOUR = 5;

export function detectEfficiency({ appliances, nightBaseKw, flatRate, days }) {
  const notes = [];
  if (nightBaseKw >= FLOOR_NOTE_KW) {
    const fridgeW = BENCHMARKS.fridge.typical_modern_kwh_per_year * 1000 / (24 * 365);
    notes.push({ kind: 'floor', confidence: 'low',
      text: t('calc.eff_floor', { watts: Math.round(nightBaseKw * 1000), kwh_year: Math.round(BENCHMARKS.fridge.typical_modern_kwh_per_year), fridge_w: Math.round(fridgeW) }),
      annualNis: nightBaseKw * 24 * 365 * flatRate });
  }
  const washers = appliances.filter(a => a.kind === 'washing_machine' && (a.confidence === 'high' || a.confidence === 'medium'));
  if (washers.length >= WASHER_MIN_EVENTS) {
    const meanCycle = washers.reduce((s, a) => s + a.excessKwh, 0) / washers.length;
    const typical = BENCHMARKS.washer.typical_modern_kwh_per_cycle;
    if (meanCycle > typical * WASHER_NOTE_RATIO) {
      const diffNis = (meanCycle - typical) * (washers.length / days * 365) * flatRate;
      notes.push({ kind: 'washer', confidence: 'medium',
        text: t('calc.eff_washer', { mean: meanCycle.toFixed(1), count: washers.length, typical: typical.toFixed(1) }),
        annualNis: diffNis });
    }
  }
  const sustained = appliances.filter(a => a.kind === 'sustained_high');
  if (sustained.length >= SUSTAINED_MIN_EVENTS) {
    const meanExKw = sustained.reduce((s, a) => s + a.excessKwh / ((a.end - a.start) / 3600e3), 0) / sustained.length;
    if (meanExKw >= SUSTAINED_MIN_MEAN_EXCESS_KW) {
      const lo = Math.round(BENCHMARKS.ac.inverter_savings_min * 100);
      const hi = Math.round(BENCHMARKS.ac.inverter_savings_max * 100);
      notes.push({ kind: 'sustained', confidence: 'low',
        text: t('calc.eff_sustained', { count: sustained.length, lo, hi }),
        annualNis: null });
    }
  }
  const unattended = appliances.filter(a => a.start.getHours() < UNATTENDED_START_HOUR);
  if (unattended.length) {
    const annualKwh = unattended.reduce((s, a) => s + a.excessKwh, 0) / days * 365;
    notes.push({ kind: 'unattended', confidence: 'medium',
      text: t('calc.eff_unattended', { count: unattended.length }),
      annualNis: annualKwh * flatRate });
  }
  return notes;
}

export function buildInsights(intervals) {
  const sum = summarize(intervals);
  const days = [...sum.daily.keys()].sort();
  const values = [...sum.daily.values()];
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const std = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length);
  const notable = days.filter(d => sum.daily.get(d) > mean + 2 * std);
  const weekday = days.filter(d => !FRI_SAT.has(new Date(d + 'T12:00:00').getDay()));
  const weekend = days.filter(d => FRI_SAT.has(new Date(d + 'T12:00:00').getDay()));
  const avg = list => list.reduce((s, d) => s + sum.daily.get(d), 0) / (list.length || 1);
  const saturdays = [...new Set(days.map(d => {
    const dt = new Date(d + 'T12:00:00');
    dt.setDate(dt.getDate() + (6 - dt.getDay()) % 7);
    return dt.getTime();
  }))].sort().map(t => new Date(t));
  const windows = saturdays.map(shabbatWindow);
  const inShabbat = dt => windows.some(([a, b]) => dt >= a && dt < b);
  const nightIvs = intervals.filter(i => i.start.getHours() >= 2 && i.start.getHours() < 5);
  const baseIvs = nightIvs.filter(i => !inShabbat(i.start));
  const shabbatNightIvs = nightIvs.filter(i => inShabbat(i.start));
  const hours = intervalHours(intervals);
  const nightBaseKw = baseIvs.length ? baseIvs.reduce((s, i) => s + i.kwh, 0) / baseIvs.length / hours : 0;
  const shabbatNightKw = shabbatNightIvs.length ? shabbatNightIvs.reduce((s, i) => s + i.kwh, 0) / shabbatNightIvs.length / hours : 0;
  const shabbatKwh = windows.map(() => 0);
  intervals.forEach(i => {
    const n = windows.findIndex(([a, b]) => i.start >= a && i.start < b);
    if (n >= 0) shabbatKwh[n] += i.kwh;
  });
  const usedShabbatot = shabbatKwh.filter(v => v > 0);
  let peakKwh = 0, peakCost = 0, totalCost = 0;
  for (const i of intervals) {
    const r = taozRate(i.start, TARIFFS.taoz);
    totalCost += i.kwh * r;
    if (taozIsPeak(i.start, TARIFFS.taoz)) { peakKwh += i.kwh; peakCost += i.kwh * r; }
  }
  // per-hour averages (sum per clock hour / days), matching the CLI units
  const hourTotals = new Array(24).fill(0);
  intervals.forEach(i => { hourTotals[i.start.getHours()] += i.kwh; });
  const peakHours = hourTotals.map((v, h) => [h, v / days.length]).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const appliances = detectAppliances(intervals, nightBaseKw);
  const inShabbatStart = e => inShabbat(e.start);
  const observance = detectShabbatObservance({
    shabbatCount: usedShabbatot.length,
    weekdayDays: weekday.length,
    nightBaseKw,
    shabbatNightBaseKw: shabbatNightKw,
    shabbatStarts: appliances.filter(inShabbatStart).length,
    weekdayStarts: appliances.filter(e => !inShabbatStart(e)).length,
  });
  return {
    days: days.length, first: days[0], last: days[days.length - 1],
    coversFullYear: days.length >= 350,
    peakHours, weekdayAvg: avg(weekday), weekendAvg: avg(weekend), nightBaseKw,
    notableDays: notable,
    taozPeakKwh: peakKwh, taozPeakCostShare: totalCost ? peakCost / totalCost : 0,
    appliances,
    shabbatCount: usedShabbatot.length,
    observance,
    efficiency: detectEfficiency({ appliances, nightBaseKw, flatRate: TARIFFS.regulated.flat_rate_per_kwh, days: days.length }),
    shabbatAvgKwh: usedShabbatot.length ? usedShabbatot.reduce((s, v) => s + v, 0) / usedShabbatot.length : 0,
    shabbatNightBaseKw: shabbatNightKw,
  };
}
