// Translations - i18n/strings.json is the single source of truth (bundled here
// as i18n-data.js by scripts/gen_web_data.py; local file, no network).
import { I18N } from './i18n-data.js';

// Every language is one block in the catalog (code, own name, dir,
// machine_draft, optional locale); nothing here names a language.
export function defaultLang() {
  for (const [code, meta] of Object.entries(I18N.languages)) if (meta.default) return code;
  return Object.keys(I18N.languages)[0];
}

// og:locale for a language: its catalog `locale`, else the bare code.
export function ogLocale(lang) {
  return (I18N.languages[lang] && I18N.languages[lang].locale) || lang;
}

// Amounts keep the default language's number grouping in every UI language
// (unchanged behavior); the locale comes from the catalog, e.g. xx_YY -> xx-YY.
export function amountLocale() {
  return ogLocale(defaultLang()).replace('_', '-');
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
  if (locale) locale.setAttribute('content', ogLocale(lang));
  for (const el of doc.querySelectorAll('[data-i18n]')) {
    const key = el.getAttribute('data-i18n');
    if (el.hasAttribute('data-i18n-alt')) el.setAttribute('alt', t(key, {}, lang));
    else el.textContent = t(key, {}, lang);
  }
  for (const el of doc.querySelectorAll('[data-i18n-title]')) {
    doc.title = t(el.getAttribute('data-i18n-title'), {}, lang);
  }
  // Carry the language through internal page links (guide/sources/back), so
  // navigation stays in the selected language. Only relative page targets
  // ("guide.html", "./", "./sources.html"); never external, assets, or pure
  // #anchors. Idempotent: any existing query string is replaced.
  for (const a of doc.querySelectorAll('a[href]')) {
    const m = a.getAttribute('href').match(/^((?:\.\/)?[\w.-]*(?:\.html)?)(\?[^#]*)?(#.*)?$/);
    if (!m) continue;
    const base = m[1];
    if (base !== './' && !base.endsWith('.html')) continue;
    a.setAttribute('href', `${base}?lang=${lang}${m[3] || ''}`);
  }
  // Dropdown selector in the header: one option per catalog language, in
  // catalog order, labelled with the language's own name (endonym) and marked
  // with its lang/dir so each name renders correctly; native select (keyboard
  // + screen-reader friendly), no reload - update the URL param and re-render.
  const sel = doc.getElementById('langSwitch');
  if (sel) {
    sel.setAttribute('aria-label', t('ui.lang_switch_label', {}, lang));
    const codes = Object.keys(I18N.languages);
    const stale = !sel.options || sel.options.length !== codes.length
      || [...sel.options].some((o, i) => o.value !== codes[i] || o.textContent !== I18N.languages[codes[i]].name);
    if (stale) {
      sel.replaceChildren();
      for (const code of codes) {
        const opt = doc.createElement('option');
        opt.value = code;
        opt.textContent = I18N.languages[code].name;
        opt.setAttribute('lang', code);
        opt.setAttribute('dir', I18N.languages[code].dir);
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
