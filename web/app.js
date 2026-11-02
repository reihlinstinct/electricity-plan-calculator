import { TARIFFS } from './tariffs-data.js';
import { parseCsv, summarize, rankPlans, buildInsights } from './calc.js';
import { t, applyI18n } from './i18n.js';

applyI18n();

const $ = id => document.getElementById(id);
const nis = v => `${Math.round(v).toLocaleString('he-IL')} ₪`;

$('csv').addEventListener('change', () => { $('go').disabled = !$('csv').files.length; });

let lastIntervals = null;
let lastErrorNoRows = false;

// (re)populate the current-plan select in the active language, keeping the
// chosen plan (by position - labels change with the language)
function populatePlanSelect() {
  const sel = $('currentPlan');
  const idx = sel.selectedIndex;
  const placeholder = sel.querySelector('option[value=""]');
  const labels = [t('plan.flat_label'), t('plan.taoz_label'),
    ...TARIFFS.supplier_plans.map(p => `${p.supplier} - ${p.plan}`)];
  sel.replaceChildren();
  if (placeholder) sel.appendChild(placeholder);
  for (const l of labels) { const o = document.createElement('option'); o.value = l; o.textContent = l; sel.appendChild(o); }
  sel.selectedIndex = idx >= 0 ? idx : 0;
}
populatePlanSelect();

function axis(ctx, w, h, pad) {
  ctx.strokeStyle = '#999'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, 10); ctx.lineTo(pad, h - pad); ctx.lineTo(w - 10, h - pad); ctx.stroke();
}

function barChart(canvas, labels, values, color) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height, pad = 40;
  ctx.clearRect(0, 0, w, h); axis(ctx, w, h, pad);
  const max = Math.max(...values, 0.001);
  const bw = (w - pad - 20) / values.length;
  values.forEach((v, i) => {
    const bh = (v / max) * (h - pad - 20);
    ctx.fillStyle = color;
    ctx.fillRect(pad + i * bw + 1, h - pad - bh, bw - 2, bh);
  });
  ctx.fillStyle = '#333'; ctx.font = '11px sans-serif'; ctx.textAlign = 'center';
  labels.forEach((l, i) => { if (l !== null) ctx.fillText(l, pad + i * bw + bw / 2, h - pad + 14); });
  ctx.textAlign = 'right';
  ctx.fillText(max.toFixed(1), pad - 4, 20);
}

function plansChart(canvas, plans, currentLabel) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height, pad = 8, labelW = 250;
  ctx.clearRect(0, 0, w, h);
  const max = Math.max(...plans.map(p => p.annual));
  const bh = Math.min(20, (h - 10) / plans.length - 4);
  ctx.font = '12px sans-serif';
  plans.forEach((p, i) => {
    const y = 8 + i * (bh + 4);
    const bwv = (p.annual / max) * (w - labelW - 80);
    ctx.fillStyle = i === 0 ? '#2e7d32' : (p.label === currentLabel ? '#0b6bcb' : '#90a4ae');
    ctx.fillRect(w - 8 - bwv, y, bwv, bh); // RTL: bars grow leftward
    ctx.fillStyle = '#333'; ctx.textAlign = 'right';
    ctx.fillText(p.label.length > 32 ? p.label.slice(0, 31) + '…' : p.label, w - 10 - bwv - 6, y + bh - 6);
    ctx.textAlign = 'left';
    ctx.fillText(nis(p.annual), 4, y + bh - 6);
  });
}

function renderAnalysis(intervals) {
    const sum = summarize(intervals);

    $('summaryCard').style.display = '';
    const sumEl = $('summary');
    sumEl.innerHTML = '';
    const daysB = document.createElement('b');
    daysB.textContent = t('app.days_measured', { days: sum.days });
    sumEl.appendChild(daysB);
    sumEl.appendChild(document.createTextNode(t('app.summary_line', {
      total: sum.total.toFixed(1), avg: (sum.total / sum.days).toFixed(2),
      annual: Math.round(sum.total / sum.days * 365).toLocaleString('he-IL') })));
    barChart($('chHourly'), [...Array(24).keys()].map(h => h % 2 ? null : `${h}:00`),
      [...sum.hourlyAvg], '#0b6bcb');
    const days = [...sum.daily.keys()].sort();
    barChart($('chDaily'), days.map((d, i) => i % Math.ceil(days.length / 12) ? null : d.slice(5)),
      days.map(d => sum.daily.get(d)), '#00897b');

    const opts = {
      phase: $('phase').value,
      smartMeter: $('smartMeter').checked,
      gasCustomer: $('gasCustomer').checked,
      hotCustomer: $('hotCustomer').checked,
    };
    const ranked = rankPlans(intervals, opts);
    const currentLabel = $('currentPlan').value || null;
    const current = currentLabel ? ranked.find(p => p.label === currentLabel) : null;

    $('plansCard').style.display = '';
    plansChart($('chPlans'), ranked.slice(0, 14), currentLabel);
    const tbl = $('plansTable');
    tbl.innerHTML = '';
    const head = tbl.insertRow();
    for (const h of ['#', t('app.col_plan'), t('app.col_annual'), t('app.col_saving')]) {
      const th = document.createElement('th'); th.textContent = h; head.appendChild(th);
    }
    ranked.forEach((p, i) => {
      const row = tbl.insertRow();
      if (i === 0) row.className = 'best';
      if (p.label === currentLabel) row.className += ' current';
      row.insertCell().textContent = String(i + 1);
      row.insertCell().textContent =
        p.label + (i === 0 ? t('app.best_marker') : '') + (p.label === currentLabel ? t('app.current_marker') : '');
      row.insertCell().textContent = nis(p.annual);
      row.insertCell().textContent = nis(p.saving);
    });
    const note = $('currentPlanNote');
    note.innerHTML = '';
    if (current) {
      const b = document.createElement('b');
      b.textContent = current === ranked[0]
        ? t('app.current_is_best', { label: current.label })
        : t('app.switch_saves', { best: ranked[0].label, amount: nis(current.annual - ranked[0].annual), label: current.label });
      const p = document.createElement('p'); p.appendChild(b); note.appendChild(p);
    }
    $('plansNote').textContent = t('app.plans_note');

    // insights: observations only, from the CSV alone
    const ins = buildInsights(intervals);
    const HEDAY = [0,1,2,3,4,5,6].map(i => t('app.day_' + i));
    const fmtD = iso => iso.slice(8, 10) + '.' + iso.slice(5, 7);
    const baseAnnual = ins.nightBaseKw * 24 * 365 * TARIFFS.regulated.flat_rate_per_kwh;
    $('insightsCard').style.display = '';
    const insText = $('insightsText');
    insText.replaceChildren();
    const addP = build => {
      const p = document.createElement('p');
      build(p);
      insText.appendChild(p);
    };
    addP(p => {
      if (ins.coversFullYear) {
        p.textContent = t('app.coverage_full', { days: ins.days, first: fmtD(ins.first), last: fmtD(ins.last) });
      } else {
        const b = document.createElement('b');
        b.textContent = t('app.coverage_partial_days', { days: ins.days });
        p.appendChild(b);
        p.append(t('app.coverage_partial_note'));
      }
    });
    addP(p => {
      p.textContent = t('app.peak_line', {
        hours: ins.peakHours.map(([h, v]) => `${String(h).padStart(2, '0')}:00 (${v.toFixed(2)})`).join(', '),
        weekday: ins.weekdayAvg.toFixed(2), weekend: ins.weekendAvg.toFixed(2),
        watts: Math.round(ins.nightBaseKw * 1000), nis: Math.round(baseAnnual).toLocaleString('he-IL') });
    });
    if (ins.shabbatCount) {
      addP(p => {
        p.textContent = t('app.shabbat_line', {
          count: ins.shabbatCount, avg: ins.shabbatAvgKwh.toFixed(1),
          shabbat: Math.round(ins.shabbatNightBaseKw * 1000), base: Math.round(ins.nightBaseKw * 1000) });
      });
    }
    if (ins.observance) {
      const ob = ins.observance;
      const pct = Math.round((ob.baseRatio - 1) * 100);
      const baseTxt = t('app.obs_base', { pct });
      const applTxt = t('app.obs_appl', { starts: ob.shabbatStarts, count: ob.shabbatCount, rate: ob.weekdayRate.toFixed(1) });
      const detail = ob.confidence === 'high' ? baseTxt + t('app.obs_join') + applTxt
        : ob.signals.includes('base') ? baseTxt + t('app.obs_base_note') : applTxt;
      const level = ob.confidence === 'high' ? t('app.level_high') : t('app.level_medium');
      const lead = ob.confidence === 'high' ? t('app.obs_lead_high') : t('app.obs_lead_medium');
      addP(p => {
        p.textContent = t('app.obs_line', { lead, level, detail });
      });
    }
    if (ins.notableDays.length) {
      addP(p => { p.textContent = t('app.notable_days', { days: ins.notableDays.map(fmtD).join(', ') }); });
    }
    addP(p => {
      p.textContent = t('app.taoz_peak', { kwh: ins.taozPeakKwh.toFixed(0), pct: (ins.taozPeakCostShare * 100).toFixed(0) });
    });
    const renderEfficiency = () => {
      if (!ins.efficiency || !ins.efficiency.length) return;
      const headP = document.createElement('p');
      const hb = document.createElement('b');
      hb.textContent = t('app.eff_header');
      headP.appendChild(hb);
      appText.appendChild(headP);
      const ul = document.createElement('ul');
      for (const n of ins.efficiency) {
        const li = document.createElement('li');
        li.textContent = n.text + ` (${CONF[n.confidence]})` +
          (n.annualNis != null ? t('app.eff_annual', { nis: Math.round(n.annualNis).toLocaleString('he-IL') }) : '');
        ul.appendChild(li);
      }
      appText.appendChild(ul);
      const srcP = document.createElement('p');
      srcP.textContent = t('app.eff_sources');
      appText.appendChild(srcP);
    };
    const KINDS = { washing_machine: t('app.kind_washing_machine'), oven: t('app.kind_oven'),
      sustained_high: t('app.kind_sustained_high') };
    const CONF = { high: t('app.confidence_high'), medium: t('app.confidence_medium'), low: t('app.confidence_low') };
    const fmtT = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    const appText = $('applianceText');
    appText.replaceChildren();
    if (ins.appliances.length) {
      const headB = document.createElement('b');
      headB.textContent = t('app.appliances_header');
      const headP = document.createElement('p');
      headP.appendChild(headB);
      appText.appendChild(headP);
      const ul = document.createElement('ul');
      for (const [kind, label] of Object.entries(KINDS)) {
        const evs = ins.appliances.filter(e => e.kind === kind);
        if (!evs.length) continue;
        const confs = {};
        evs.forEach(e => { confs[e.confidence] = (confs[e.confidence] || 0) + 1; });
        const li = document.createElement('li');
        li.textContent = t('app.appliance_line', { label, count: evs.length, confs: Object.entries(confs).map(([c, n]) => t('app.appliance_conf_part', { n, conf: CONF[c] })).join(', ') });
        const sub = document.createElement('ul');
        for (const e of evs.slice().sort((x, y) => y.excessKwh - x.excessKwh).slice(0, 2)) {
          const ex = document.createElement('li');
          ex.textContent = t('app.appliance_example', {
            day: HEDAY[e.start.getDay()],
            date: String(e.start.getDate()).padStart(2, '0') + '.' + String(e.start.getMonth() + 1).padStart(2, '0'),
            start: fmtT(e.start), end: fmtT(e.end), kwh: e.excessKwh.toFixed(1), conf: CONF[e.confidence], pattern: e.pattern });
          sub.appendChild(ex);
        }
        li.appendChild(sub);
        ul.appendChild(li);
      }
      appText.appendChild(ul);
    }
    renderEfficiency();
}

$('go').addEventListener('click', async () => {
  const err = $('err'); err.style.display = 'none';
  try {
    const text = await $('csv').files[0].text();
    lastIntervals = parseCsv(text);
    lastErrorNoRows = false;
    renderAnalysis(lastIntervals);
    $('status').textContent = '';
  } catch (e) {
    lastErrorNoRows = e.message === t('calc.err_no_rows');
    err.textContent = e.message; err.style.display = '';
    $('status').textContent = '';
  }
});

// Language switch re-renders every dynamically built string (select options,
// results, tables, insights, a visible validation error) - applyI18n handles
// the static markup; this event covers the rest.
document.addEventListener('iec:langchange', () => {
  populatePlanSelect();
  if (lastIntervals) renderAnalysis(lastIntervals);
  else if (lastErrorNoRows) $('err').textContent = t('calc.err_no_rows');
});
