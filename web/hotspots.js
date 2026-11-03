// Translation hotspots over the Hebrew IEC guide screenshots (#67).
// % coordinates over the Hebrew UI elements the guide text references;
// hover/focus/tap shows the term in the current language. Hebrew UI needs
// no gloss - hotspots render only for other languages. Coordinates are tied
// to the current screenshots: replacing one means re-placing its hotspots.
import { t, currentLang } from './i18n.js';

export const HOTSPOTS = {
  step1: [{ k: 'guide.hs_quick_actions', x: 84, y: 15, w: 15, h: 75 },
          { k: 'guide.hs_all_actions', x: 0, y: 3, w: 10, h: 94 }],
  step2: [{ k: 'guide.hs_all_actions', x: 82, y: 3, w: 14, h: 18 },
          { k: 'guide.hs_meters', x: 59, y: 24, w: 20, h: 74 }],
  step3: [{ k: 'guide.hs_meters', x: 25, y: 27, w: 50, h: 14 },
          { k: 'guide.hs_activity', x: 2, y: 52, w: 96, h: 11 }],
  step4: [{ k: 'guide.hs_which_data', x: 30, y: 8, w: 46, h: 10 },
          { k: 'guide.hs_current', x: 51, y: 16, w: 46, h: 32 }],
  step5: [{ k: 'guide.hs_by_period', x: 8, y: 5, w: 43, h: 12 },
          { k: 'guide.hs_meter_consumption', x: 27, y: 20, w: 43, h: 7 }],
  step6: [{ k: 'guide.hs_send_excel', x: 15, y: 4, w: 80, h: 36 }],
};

// A touch tap fires mouseenter (show) immediately before click; without a
// guard that same tap would toggle the tip straight back off (#68 review).
const CLICK_SUPPRESS_MS = 500;

export function hideTips(doc = document) {
  doc.querySelectorAll('.hs-tip').forEach(e => e.remove());
  doc.querySelectorAll('.hs.on').forEach(e => {
    e.classList.remove('on');
    e.removeAttribute('aria-describedby');
    e._pinned = false;
  });
}

export function renderHotspots(doc = document) {
  hideTips(doc);
  doc.querySelectorAll('.hs').forEach(e => e.remove());
  const lang = currentLang();
  const hint = doc.getElementById('hsHint');
  if (hint) {
    hint.textContent = t('guide.hs_hint', {}, lang);
    hint.style.display = lang === 'he' ? 'none' : '';
  }
  if (lang === 'he') return;
  let tipSeq = 0;
  for (const [shot, list] of Object.entries(HOTSPOTS)) {
    const wrap = doc.querySelector(`.shot[data-shot="${shot}"]`);
    if (!wrap) continue;
    for (const h of list) {
      const label = t(h.k, {}, lang);
      const b = doc.createElement('button');
      b.type = 'button';
      b.className = 'hs';
      b.style.left = h.x + '%'; b.style.top = h.y + '%';
      b.style.width = h.w + '%'; b.style.height = h.h + '%';
      b.setAttribute('aria-label', label);
      const show = () => {
        hideTips(doc);
        b.classList.add('on');
        b._shownAt = Date.now();
        const tip = doc.createElement('div');
        tip.className = 'hs-tip';
        tip.id = `hs-tip-${++tipSeq}`;
        tip.setAttribute('role', 'tooltip');
        tip.textContent = label;
        if (h.x > 50) tip.style.right = Math.max(100 - h.x - h.w, 0) + '%';
        else tip.style.left = h.x + '%';
        // adjacent, not on top: below the hotspot when it sits in the upper
        // part of the image, above it once its center passes the middle or
        // it reaches the bottom edge (#69 - bubbles overlapping labels)
        if (h.y + h.h / 2 > 50 || h.y + h.h > 85) tip.style.bottom = (100 - h.y + 1) + '%';
        else tip.style.top = (h.y + h.h + 1) + '%';
        wrap.appendChild(tip);
        b.setAttribute('aria-describedby', tip.id);
      };
      b.addEventListener('mouseenter', show);
      b.addEventListener('focus', show);
      b.addEventListener('mouseleave', () => { if (!b._pinned) hideTips(doc); });
      b.addEventListener('blur', () => { if (!b._pinned) hideTips(doc); });
      b.addEventListener('click', ev => {
        ev.stopPropagation();
        if (b.classList.contains('on') && Date.now() - b._shownAt > CLICK_SUPPRESS_MS) {
          b._pinned = false;
          hideTips(doc);
        } else {
          show();
          b._pinned = true;
        }
      });
      wrap.appendChild(b);
    }
  }
}

export function initHotspots(doc = document) {
  renderHotspots(doc);
  doc.addEventListener('iec:langchange', () => renderHotspots(doc));
  doc.addEventListener('click', ev => {
    if (!ev.target || !ev.target.classList || !ev.target.classList.contains('hs')) hideTips(doc);
  });
  doc.addEventListener('keydown', ev => { if (ev.key === 'Escape') hideTips(doc); });
}
