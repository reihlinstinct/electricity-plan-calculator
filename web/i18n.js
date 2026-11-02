// Translations - i18n/strings.json is the single source of truth (bundled here
// as i18n-data.js by scripts/gen_web_data.py; local file, no network).
import { I18N } from './i18n-data.js';

export function defaultLang() {
  for (const [code, meta] of Object.entries(I18N.languages)) if (meta.default) return code;
  return Object.keys(I18N.languages)[0];
}

// ?lang= keeps the choice in the URL: shareable, no cookies, no storage.
export function currentLang() {
  if (typeof location === 'undefined') return defaultLang(); // node (tests)
  const q = new URLSearchParams(location.search).get('lang');
  return q && I18N.languages[q] ? q : defaultLang();
}

export function t(key, params = {}, lang = currentLang()) {
  const entry = I18N.strings[key];
  if (!entry) return key;
  const template = entry[lang] || entry[defaultLang()];
  if (template == null) return key;
  return template.replace(/\{(\w+)\}/g, (m, name) =>
    params[name] !== undefined ? String(params[name]) : m);
}

// Fill [data-i18n] elements, set <html lang dir>, render the top selector.
export function applyI18n(doc = document) {
  const lang = currentLang();
  const meta = I18N.languages[lang];
  doc.documentElement.lang = lang;
  doc.documentElement.dir = meta.dir;
  // per-language og/twitter meta (JS-only: server-side scrapers that do not
  // run JavaScript still see the default-language tags baked into the HTML)
  const og = { 'og:title': 'ui.og_title', 'og:description': 'ui.og_desc' };
  for (const [prop, key] of Object.entries(og)) {
    const el = doc.querySelector(`meta[property="${prop}"]`);
    if (el && I18N.strings[key]) el.setAttribute('content', t(key, {}, lang));
  }
  for (const name of ['twitter:title', 'twitter:description']) {
    const key = name === 'twitter:title' ? 'ui.og_title' : 'ui.og_desc';
    const el = doc.querySelector(`meta[name="${name}"]`);
    if (el && I18N.strings[key]) el.setAttribute('content', t(key, {}, lang));
  }
  const locale = doc.querySelector('meta[property="og:locale"]');
  if (locale) locale.setAttribute('content', { he: 'he_IL', en: 'en_US' }[lang] || lang);
  for (const el of doc.querySelectorAll('[data-i18n]')) {
    const key = el.getAttribute('data-i18n');
    if (el.hasAttribute('data-i18n-alt')) el.setAttribute('alt', t(key, {}, lang));
    else el.textContent = t(key, {}, lang);
  }
  for (const el of doc.querySelectorAll('[data-i18n-title]')) {
    doc.title = t(el.getAttribute('data-i18n-title'), {}, lang);
  }
  // Dropdown selector in the header: 2-letter codes, native select (keyboard
  // + screen-reader friendly), no reload - update the URL param and re-render.
  const sel = doc.getElementById('langSwitch');
  if (sel) {
    sel.setAttribute('aria-label', t('ui.lang_switch_label', {}, lang));
    const codes = Object.keys(I18N.languages);
    const stale = !sel.options || sel.options.length !== codes.length
      || [...sel.options].some((o, i) => o.value !== codes[i] || o.textContent !== codes[i].toUpperCase());
    if (stale) {
      sel.replaceChildren();
      for (const code of codes) {
        const opt = doc.createElement('option');
        opt.value = code;
        opt.textContent = code.toUpperCase();
        sel.appendChild(opt);
      }
    }
    if (!sel.dataset || !sel.dataset.langBound) {
      (sel.dataset ||= {}).langBound = '1';
      sel.addEventListener('change', () => {
        const q = new URLSearchParams(window.location.search);
        q.set('lang', sel.value);
        window.history.replaceState(null, '', `${window.location.pathname}?${q}${window.location.hash}`);
        applyI18n();
        doc.dispatchEvent(new (window.CustomEvent || CustomEvent)('iec:langchange'));
      });
    }
    sel.value = lang;
  }
}
