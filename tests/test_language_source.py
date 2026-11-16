"""Tripwire: the catalog (i18n/strings.json) is the only place that names languages.

Any language code from the catalog written as a literal in source or tests
fails here, unless the exact line is on the short, justified allow-list
below. The codes are read from the catalog, so a newly added language is
covered automatically. Docs that list the languages are generated from the
catalog (scripts/gen_language_lists.py) and checked for freshness.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "i18n" / "strings.json").read_text(encoding="utf-8"))
CODES = list(DOC["languages"])
DEFAULT = next(code for code, meta in DOC["languages"].items() if meta.get("default"))

SCANNED = ["src/**/*.py", "scripts/**/*.py", "scripts/**/*.sh", "setup.py", "web/*.js", "web/*.html"]
SCANNED += ["tests/**/*.py", "tests/**/*.mjs"]
# The generated web bundle is a copy of the catalog itself.
NOT_SCANNED = {"web/i18n-data.js"}

# (path, regex for the whole stripped line, reason). Keep this short.
HTML_ROOT = r'<html lang="[a-z]{2,3}" dir="(rtl|ltr)">'
ALLOWED = [
    ("web/index.html", HTML_ROOT, "static default-language markup for readers without JavaScript (checked below)"),
    ("web/guide.html", HTML_ROOT, "static default-language markup for readers without JavaScript (checked below)"),
    ("web/sources.html", HTML_ROOT, "static default-language markup for readers without JavaScript (checked below)"),
    (
        "web/index.html",
        r'<meta property="og:locale" content="[a-z]{2,3}_[A-Z]{2}">',
        "default og:locale for link scrapers that do not run JavaScript (checked below)",
    ),
    (
        "scripts/generate_og_assets.py",
        r'.*\bdirection="rtl", language="[a-z]{2,3}"\)',
        "text-shaping language for the fixed Hebrew strings this dev script draws into og-image.png",
    ),
    (
        "tests/web_calc.test.mjs",
        r"const PIN = '[a-z]{2,3}';.*",
        "the functional language-switch test pins rendered text of one second language",
    ),
]

_ALT = "(?:" + "|".join(map(re.escape, CODES)) + ")"
PATTERNS = [
    # a quoted code, optionally with a region: xx, xx_YY, xx-YY
    re.compile(r"""(?<![\w-])(["'`])""" + _ALT + r"(?:[-_][A-Za-z]{2,4})?\1"),
    # a ?lang=xx URL parameter
    re.compile(r"\blang=" + _ALT + r"\b"),
]
JS_PATTERNS = [
    re.compile(r"\." + _ALT + r"\b(?![\w(])"),  # property access, I18N.languages.xx
    re.compile(r"[{,]\s*" + _ALT + r"\s*:"),  # object key, { xx: ... }
]


def _files():
    seen = set()
    for pattern in SCANNED:
        for path in sorted(ROOT.glob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            if rel in NOT_SCANNED or rel in seen or "__pycache__" in rel:
                continue
            seen.add(rel)
            yield rel, path


def _allowed(rel, line):
    return any(rel == path and re.fullmatch(rx, line.strip()) for path, rx, _ in ALLOWED)


def find_hardcoded():
    hits = []
    for rel, path in _files():
        patterns = PATTERNS + (JS_PATTERNS if rel.endswith((".js", ".mjs")) else [])
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in patterns) and not _allowed(rel, line):
                hits.append(f"{rel}:{n}: {line.strip()}")
    return hits


def test_no_language_code_hardcoded_outside_the_catalog():
    hits = find_hardcoded()
    assert not hits, "language codes must come from i18n/strings.json; found:\n" + "\n".join(hits)


@pytest.mark.parametrize("path,rx,reason", ALLOWED)
def test_allow_list_entries_are_still_needed(path, rx, reason):
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    assert any(re.fullmatch(rx, ln.strip()) for ln in lines), f"stale allow-list entry for {path}: {reason}"


def test_scanner_sees_a_stray_code():
    code = CODES[-1]
    probe = re.compile("|".join(p.pattern for p in PATTERNS + JS_PATTERNS))
    for sample in (f"x = '{code}'", f'lang="{code}"', f"?lang={code}", f"I18N.languages.{code}", f"{{ {code}: 1 }}"):
        assert probe.search(sample), sample


@pytest.mark.parametrize("page", ["index.html", "guide.html", "sources.html"])
def test_static_html_matches_the_default_language(page):
    body = (ROOT / "web" / page).read_text(encoding="utf-8")
    meta = DOC["languages"][DEFAULT]
    assert f'<html lang="{DEFAULT}" dir="{meta["dir"]}">' in body
    if page == "index.html":
        assert f'<meta property="og:locale" content="{meta["locale"]}">' in body


def test_language_lists_in_docs_are_generated_from_the_catalog():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_language_lists.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
