// Pure calculation core - no DOM, testable in node. Mirrors src/iec_calc/*.
import { TARIFFS } from './tariffs-data.js';

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
      const kwh = parseFloat(cells[4]) || 0, feed = parseFloat(cells[5]) || 0;
      const start = new Date(yyyy, mm - 1, dd, hh === 24 ? 0 : hh, hh === 24 ? 0 : mi);
      if (hh === 24) start.setDate(start.getDate() + 1);
      intervals.push({ start, kwh, feed });
    }
  }
  if (!intervals.length) throw new Error('לא נמצאו שורות צריכה בקובץ. ודאו שזה ייצוא צריכה של חברת החשמל.');
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
export function taozRate(when, taoz) {
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
  return peak ? s.rates.peak : s.rates.off_peak;
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
  out.push({ label: 'חברת החשמל - תעריף אחיד מפוקח', kind: 'flat', annual: flatAnnual, saving: 0 });
  const taozEnergy = intervals.reduce((s, i) => s + i.kwh * taozRate(i.start, TARIFFS.taoz), 0);
  const taozAnnual = ann(taozEnergy) + taozFixed;
  out.push({ label: 'תעו"ז מפוקח (מונה חכם)', kind: 'taoz', annual: taozAnnual, saving: flatAnnual - taozAnnual });
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
