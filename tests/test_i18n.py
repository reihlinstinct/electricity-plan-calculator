"""i18n/strings.json integrity: the catalog is the only language source.

Every language is one block under "languages" (code = the block's key, own
name, direction, machine-draft flag, optional og/number locale). Tests below
discover the languages from that map only; content pins per language live in
tests/fixtures/i18n_pins.json and are optional, so adding a language needs no
test change.
"""

import json
import re
from pathlib import Path

import pytest

import iec_calc.i18n as i18n

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "i18n" / "strings.json").read_text(encoding="utf-8"))
PINS = json.loads((ROOT / "tests" / "fixtures" / "i18n_pins.json").read_text(encoding="utf-8"))
PLACEHOLDER = re.compile(r"\{(\w+)\}")
LANGS = list(DOC["languages"])
DEFAULT = next(code for code, meta in DOC["languages"].items() if meta.get("default"))
OTHERS = [code for code in LANGS if code != DEFAULT]
BLOCK_FIELDS = {"name", "dir", "default", "machine_draft", "locale"}


def test_every_key_exists_in_every_language():
    missing = [(key, lang) for key, entry in DOC["strings"].items() for lang in LANGS if not entry.get(lang)]
    assert not missing, f"keys missing a translation: {missing[:5]}"


def test_no_string_carries_a_language_outside_the_catalog():
    stray = sorted({lang for entry in DOC["strings"].values() for lang in entry} - set(LANGS))
    assert not stray, f"strings carry languages that have no block in 'languages': {stray}"


def test_placeholders_match_across_languages():
    for key, entry in DOC["strings"].items():
        sets = {lang: set(PLACEHOLDER.findall(text)) for lang, text in entry.items()}
        assert len({frozenset(s) for s in sets.values()}) <= 1, f"{key}: placeholders differ {sets}"


def test_exactly_one_default_language():
    assert sum(1 for m in DOC["languages"].values() if m.get("default")) == 1
    assert LANGS[0] == DEFAULT, "the default (source) language comes first in the catalog"


@pytest.mark.parametrize("code", LANGS)
def test_language_block_shape(code):
    meta = DOC["languages"][code]
    assert re.fullmatch(r"[a-z]{2,3}", code), code
    assert set(meta) <= BLOCK_FIELDS, f"{code}: unknown fields {set(meta) - BLOCK_FIELDS}"
    assert isinstance(meta.get("name"), str) and meta["name"].strip(), f"{code}: own name (endonym) missing"
    assert meta.get("dir") in ("rtl", "ltr"), code
    assert isinstance(meta.get("machine_draft"), bool), f"{code}: machine_draft must be true or false"
    if "locale" in meta:
        assert re.fullmatch(code + r"_[A-Z]{2}", meta["locale"]), f"{code}: locale {meta['locale']!r}"


def test_default_language_is_not_a_draft_and_has_a_locale():
    meta = DOC["languages"][DEFAULT]
    assert meta["machine_draft"] is False
    assert "locale" in meta, "the default language's locale drives og:locale and amount formatting"


def test_endonyms_are_unique():
    names = [m["name"] for m in DOC["languages"].values()]
    assert len(names) == len(set(names))


def test_python_loader_sees_exactly_the_catalog_languages():
    assert list(i18n.languages()) == LANGS
    assert i18n.default_lang() == DEFAULT


def test_t_substitutes_and_falls_back():
    assert i18n.t("app.days_measured", days=3) == DOC["strings"]["app.days_measured"][DEFAULT].format(days=3)
    assert i18n.t("no.such.key") == "no.such.key"
    # unknown placeholder stays visible rather than raising
    assert "{days}" in i18n.t("app.days_measured")
    # unknown language falls back to the default
    assert i18n.t("ui.title", lang="xx") == DOC["strings"]["ui.title"][DEFAULT]


@pytest.mark.parametrize("code", LANGS)
def test_t_explicit_language(code):
    assert i18n.t("ui.title", lang=code) == DOC["strings"]["ui.title"][code]
    if code != DEFAULT:
        assert i18n.t("ui.title", lang=code) != i18n.t("ui.title", lang=DEFAULT)


def test_title_pins():
    pins = PINS["ui.title"]
    assert set(pins) <= set(LANGS), f"pins for languages not in the catalog: {set(pins) - set(LANGS)}"
    for code, text in pins.items():
        assert i18n.t("ui.title", lang=code) == text, code


def test_pins_only_name_catalog_languages():
    for section, table in PINS.items():
        if isinstance(table, dict):
            stray = set(table) - set(LANGS)
            assert not stray, f"{section}: pins for languages not in the catalog: {stray}"


@pytest.mark.parametrize("code", OTHERS)
def test_set_active_language(code):
    try:
        i18n.set_active_language(code)
        assert i18n.t("ui.title") == DOC["strings"]["ui.title"][code]
        i18n.set_active_language("xx")  # unknown: back to default
        assert i18n.t("ui.title") == DOC["strings"]["ui.title"][DEFAULT]
    finally:
        i18n.set_active_language(None)
        assert i18n.t("ui.title") == DOC["strings"]["ui.title"][DEFAULT]


@pytest.mark.parametrize("code", OTHERS)
def test_cli_report_lang(code):
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    def run(*lang):
        return subprocess.run(
            [sys.executable, "-m", "iec_calc.cli", *lang, "report", "data/sample_consumption.csv"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )

    base, out = run(), run("--lang", code)
    assert base.returncode == 0 and out.returncode == 0
    title = DOC["strings"]["report.analysis_title"]
    assert title[code] in out.stdout and title[DEFAULT] not in out.stdout
    assert title[DEFAULT] in base.stdout
    # cautious phrasing survives translation (pinned per language where reviewed)
    for phrase in PINS["report_contains"].get(code, []):
        assert phrase in out.stdout, (code, phrase)


def _hvac_head(code):
    from iec_calc.report import format_hvac
    from iec_calc.weather import HvacReport, MonthAttribution

    rep = HvacReport(
        days=30,
        kwh_per_cooling_degree=1.0,
        kwh_per_heating_degree=1.0,
        r_squared=0.5,
        cooling_base=22.0,
        heating_base=18.0,
        monthly=(MonthAttribution("2026-09", 30, 300.0, 180.0, 40.0, 60.0, 20.0, 0.0),),
    )
    i18n.set_active_language(code)
    try:
        return format_hvac(rep).splitlines()[5]
    finally:
        i18n.set_active_language(None)


@pytest.mark.parametrize("code", LANGS)
def test_hvac_header_columns_separated(code):
    head = _hvac_head(code)
    # month + 6 value columns, each label its own whitespace-separated word
    assert len(head.split()) == 7, (code, head)
    never = PINS["hvac_head_never"].get(code)
    if never:
        assert never not in head
    for word in PINS["hvac_head_words"].get(code, []):
        assert word in head, (code, word)
