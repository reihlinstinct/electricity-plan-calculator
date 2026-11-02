import { TARIFFS } from './tariffs-data.js';
import { parseCsv, summarize, rankPlans, buildInsights } from './calc.js';

const $ = id => document.getElementById(id);
const nis = v => `${Math.round(v).toLocaleString('he-IL')} ₪`;

$('csv').addEventListener('change', () => { $('go').disabled = !$('csv').files.length; });

// populate current-plan select from catalog
{
  const sel = $('currentPlan');
  const labels = ['חברת החשמל - תעריף אחיד מפוקח', 'תעו"ז מפוקח (מונה חכם)',
    ...TARIFFS.supplier_plans.map(p => `${p.supplier} - ${p.plan}`)];
  for (const l of labels) { const o = document.createElement('option'); o.value = l; o.textContent = l; sel.appendChild(o); }
}
$('sources').textContent = [...new Set(TARIFFS.sources.map(s => new URL(s.url).hostname))].join(', ');

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

$('go').addEventListener('click', async () => {
  const err = $('err'); err.style.display = 'none';
  try {
    const text = await $('csv').files[0].text();
    const intervals = parseCsv(text);
    const sum = summarize(intervals);

    $('summaryCard').style.display = '';
    const sumEl = $('summary');
    sumEl.innerHTML = '';
    const daysB = document.createElement('b');
    daysB.textContent = `${sum.days} ימי מדידה`;
    sumEl.appendChild(daysB);
    sumEl.appendChild(document.createTextNode(
      ` · סה"כ ${sum.total.toFixed(1)} קוט"ש · ממוצע ${(sum.total / sum.days).toFixed(2)} קוט"ש/יום` +
      ` · הערכה שנתית ${Math.round(sum.total / sum.days * 365).toLocaleString('he-IL')} קוט"ש`));
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
    for (const t of ['#', 'מסלול', 'עלות שנתית', 'חיסכון מול תעריף אחיד']) {
      const th = document.createElement('th'); th.textContent = t; head.appendChild(th);
    }
    ranked.forEach((p, i) => {
      const row = tbl.insertRow();
      if (i === 0) row.className = 'best';
      if (p.label === currentLabel) row.className += ' current';
      row.insertCell().textContent = String(i + 1);
      row.insertCell().textContent =
        p.label + (i === 0 ? ' ◀ הכי משתלם' : '') + (p.label === currentLabel ? ' ◀ המסלול הנוכחי' : '');
      row.insertCell().textContent = nis(p.annual);
      row.insertCell().textContent = nis(p.saving);
    });
    const note = $('currentPlanNote');
    note.innerHTML = '';
    if (current) {
      const b = document.createElement('b');
      b.textContent = current === ranked[0]
        ? `המסלול הנוכחי שלך (${current.label}) הוא הזול ביותר - אין צורך להחליף.`
        : `מעבר ל${ranked[0].label} חוסך ${nis(current.annual - ranked[0].annual)} לשנה מול המסלול הנוכחי (${current.label}).`;
      const p = document.createElement('p'); p.appendChild(b); note.appendChild(p);
    }
    $('plansNote').textContent = 'בתעו"ז התשלום הקבוע גבוה יותר. מסלולי שעות דורשים מונה חכם.';

    // insights: observations only, from the CSV alone
    const ins = buildInsights(intervals);
    const HEDAY = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
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
        p.textContent = `כיסוי: ${ins.days} ימים (${fmtD(ins.first)} - ${fmtD(ins.last)}) - שנה מלאה.`;
      } else {
        const b = document.createElement('b');
        b.textContent = `כיסוי: ${ins.days} ימים בלבד.`;
        p.appendChild(b);
        p.append(' השוואה עונתית (חורף/קיץ) דורשת ייצוא של שנה מלאה; אין להסיק מהקובץ על עונות שאינן בו.');
      }
    });
    addP(p => {
      p.textContent =
        `שעות שיא ממוצעות: ${ins.peakHours.map(([h, v]) => `${String(h).padStart(2, '0')}:00 (${v.toFixed(2)})`).join(', ')} קוט"ש · ` +
        `יום חול ${ins.weekdayAvg.toFixed(2)} | שישי-שבת ${ins.weekendAvg.toFixed(2)} קוט"ש · ` +
        `רצפת צריכה (בסיס): ${Math.round(ins.nightBaseKw * 1000)} וואט (כ-${Math.round(baseAnnual).toLocaleString('he-IL')} ₪ לשנה אם קבוע) - מקרר שעובד תמיד ועוד מכשירים מחוברים שכל אחד צורך מעט; יחד הם יוצרים את הרצפה`;
    });
    if (ins.shabbatCount) {
      addP(p => {
        p.textContent =
          `שבת (שקיעת ו' עד צאת השבת, ${ins.shabbatCount} שבתות): ממוצע ${ins.shabbatAvgKwh.toFixed(1)} קוט"ש לשבת; ` +
          `צריכת לילה ${Math.round(ins.shabbatNightBaseKw * 1000)} וואט מול ${Math.round(ins.nightBaseKw * 1000)} בחול - ` +
          `עומס קבוע (למשל פלטה/מיחם) הוא הסבר אפשרי, לא ודאי`;
      });
    }
    if (ins.observance) {
      const ob = ins.observance;
      const pct = Math.round((ob.baseRatio - 1) * 100);
      const baseTxt = `צריכת ליל שבת גבוהה ב-${pct}% מליל חול`;
      const applTxt = `${ob.shabbatStarts} הפעלות מכשירים ב-${ob.shabbatCount} שבתות (מול ${ob.weekdayRate.toFixed(1)} ליום חול בממוצע)`;
      const detail = ob.confidence === 'high' ? `${baseTxt} ו${applTxt}`
        : ob.signals.includes('base') ? `${baseTxt} - עומס קבוע כמו פלטה/מיחם הוא הסבר אפשרי` : applTxt;
      const level = ob.confidence === 'high' ? 'גבוה' : 'בינוני';
      const lead = ob.confidence === 'high' ? 'נראה' : 'ייתכן';
      addP(p => {
        p.textContent = `${lead} שבמשק הבית שומרים שבת (ביטחון ${level}): ${detail}. תצפית סטטיסטית מהקובץ בלבד, לא ודאות`;
      });
    }
    if (ins.notableDays.length) {
      addP(p => { p.textContent = `ימים עם צריכה חריגה: ${ins.notableDays.map(fmtD).join(', ')}`; });
    }
    addP(p => {
      p.textContent = `חלון השיא של תעו"ז: ${ins.taozPeakKwh.toFixed(0)} קוט"ש (${(ins.taozPeakCostShare * 100).toFixed(0)}% מהעלות אם היית בתעו"ז)`;
    });
    const renderEfficiency = () => {
      if (!ins.efficiency || !ins.efficiency.length) return;
      const headP = document.createElement('p');
      const hb = document.createElement('b');
      hb.textContent = 'יעילות מכשירים (השוואה לטיפוסי מודרני, בלי פסיקה על מכשיר):';
      headP.appendChild(hb);
      appText.appendChild(headP);
      const ul = document.createElement('ul');
      for (const n of ins.efficiency) {
        const li = document.createElement('li');
        li.textContent = n.text + ` (${CONF[n.confidence]})` +
          (n.annualNis != null ? ` הערכת הפרש/עלות שנתית: ~${Math.round(n.annualNis).toLocaleString('he-IL')} ₪.` : '');
        ul.appendChild(li);
      }
      appText.appendChild(ul);
      const srcP = document.createElement('p');
      srcP.textContent = 'מקורות ההשוואה מפורטים בדף Sources (אומתו ב-2026-11-02).';
      appText.appendChild(srcP);
    };
    const KINDS = { washing_machine: 'מכונת כביסה אפשרית', oven: 'תנור אפייה אפשרי',
      sustained_high: 'עומס גבוה ממושך (ייתכן מזגן/חימום/דוד - לא ניתן להבחין מהצריכה בלבד)' };
    const CONF = { high: 'ביטחון גבוה', medium: 'ביטחון בינוני', low: 'ביטחון נמוך' };
    const fmtT = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    const appText = $('applianceText');
    appText.replaceChildren();
    if (ins.appliances.length) {
      const headB = document.createElement('b');
      headB.textContent = 'זיהוי מכשירים (הערכה הסתברותית מחתימת העומס בלבד, לא ודאות):';
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
        li.textContent = `${label}: ${evs.length} אירועים (${Object.entries(confs).map(([c, n]) => `${n} ב${CONF[c]}`).join(', ')}).`;
        const sub = document.createElement('ul');
        for (const e of evs.slice().sort((x, y) => y.excessKwh - x.excessKwh).slice(0, 2)) {
          const ex = document.createElement('li');
          ex.textContent = `למשל יום ${HEDAY[e.start.getDay()]} ${String(e.start.getDate()).padStart(2, '0')}.${String(e.start.getMonth() + 1).padStart(2, '0')} ` +
            `${fmtT(e.start)}-${fmtT(e.end)} (${e.excessKwh.toFixed(1)} קוט"ש, ${CONF[e.confidence]}): ${e.pattern}`;
          sub.appendChild(ex);
        }
        li.appendChild(sub);
        ul.appendChild(li);
      }
      appText.appendChild(ul);
    }
    renderEfficiency();

    $('status').textContent = '';
  } catch (e) {
    err.textContent = e.message; err.style.display = '';
    $('status').textContent = '';
  }
});
