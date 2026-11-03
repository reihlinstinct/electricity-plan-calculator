"""i18n/strings.json integrity: every key complete in every language, placeholders match."""
import json
import re
from pathlib import Path

import iec_calc.i18n as i18n

DOC = json.loads((Path(__file__).resolve().parent.parent / "i18n" / "strings.json").read_text(encoding="utf-8"))
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_every_key_exists_in_every_language():
    langs = set(DOC["languages"])
    missing = [
        (key, lang) for key, entry in DOC["strings"].items() for lang in langs
        if not entry.get(lang)
    ]
    assert not missing, f"keys missing a translation: {missing[:5]}"


def test_placeholders_match_across_languages():
    for key, entry in DOC["strings"].items():
        sets = {lang: set(PLACEHOLDER.findall(text)) for lang, text in entry.items()}
        assert len({frozenset(s) for s in sets.values()}) <= 1, f"{key}: placeholders differ {sets}"


def test_exactly_one_default_language():
    assert sum(1 for m in DOC["languages"].values() if m.get("default")) == 1
    for code, meta in DOC["languages"].items():
        assert meta.get("name") and meta.get("dir") in ("rtl", "ltr"), code


def test_t_substitutes_and_falls_back():
    assert i18n.t("app.days_measured", days=3) == "3 ימי מדידה"
    assert i18n.t("no.such.key") == "no.such.key"
    # unknown placeholder stays visible rather than raising
    assert "{days}" in i18n.t("app.days_measured")


def test_t_explicit_language():
    assert i18n.t("ui.title", lang="en") == "Electricity plan calculator"
    assert i18n.t("ui.title", lang="he") == "מחשבון מסלולי חשמל"
    assert i18n.t("ui.title", lang="ar") == "حاسبة مسارات الكهرباء"


def test_arabic_is_rtl_not_default():
    assert DOC["languages"]["ar"]["dir"] == "rtl"
    assert not DOC["languages"]["ar"].get("default")
    assert i18n.t("ui.title", lang="ar") != i18n.t("ui.title", lang="he")


def test_russian_is_ltr_not_default():
    assert i18n.t("ui.title", lang="ru") == "Калькулятор планов электричества"
    assert DOC["languages"]["ru"]["dir"] == "ltr"
    assert not DOC["languages"]["ru"].get("default")
    assert i18n.t("ui.title", lang="ru") != i18n.t("ui.title", lang="he")


def test_set_active_language():
    try:
        i18n.set_active_language("en")
        assert i18n.t("ui.title") == "Electricity plan calculator"
        i18n.set_active_language("xx")  # unknown: back to default
        assert i18n.t("ui.title") == "מחשבון מסלולי חשמל"
    finally:
        i18n.set_active_language("he")
        assert i18n.t("ui.title") == "מחשבון מסלולי חשמל"


def test_cli_report_lang_en():
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    base = subprocess.run(
        [sys.executable, "-m", "iec_calc.cli", "report", "data/sample_consumption.csv"],
        capture_output=True, text=True, cwd=root, env=env,
    )
    en = subprocess.run(
        [sys.executable, "-m", "iec_calc.cli", "--lang", "en", "report", "data/sample_consumption.csv"],
        capture_output=True, text=True, cwd=root, env=env,
    )
    assert base.returncode == 0 and en.returncode == 0
    assert "Consumption analysis" in en.stdout and "ניתוח צריכה" not in en.stdout
    assert "ניתוח צריכה" in base.stdout
    # cautious phrasing survives translation
    assert "not a certainty" in en.stdout
    assert "not a verdict" in en.stdout and "possible explanation" in en.stdout


def test_hvac_header_arabic_columns_separated():
    from iec_calc.report import format_hvac
    from iec_calc.weather import HvacReport, MonthAttribution
    rep = HvacReport(
        days=30, kwh_per_cooling_degree=1.0, kwh_per_heating_degree=1.0,
        r_squared=0.5, cooling_base=22.0, heating_base=18.0,
        monthly=(MonthAttribution("2026-09", 30, 300.0, 180.0, 40.0, 60.0, 20.0, 0.0),),
    )
    i18n.set_active_language("ar")
    try:
        head = format_hvac(rep).splitlines()[5]
    finally:
        i18n.set_active_language(None)
    assert "الأساسجمعة" not in head
    for word in ("الشهر", "المجموع", "الأساس", "تبريد", "تدفئة", "أخرى"):
        assert word in head


def test_hvac_header_russian_columns_separated():
    from iec_calc.report import format_hvac
    from iec_calc.weather import HvacReport, MonthAttribution
    rep = HvacReport(
        days=30, kwh_per_cooling_degree=1.0, kwh_per_heating_degree=1.0,
        r_squared=0.5, cooling_base=22.0, heating_base=18.0,
        monthly=(MonthAttribution("2026-09", 30, 300.0, 180.0, 40.0, 60.0, 20.0, 0.0),),
    )
    i18n.set_active_language("ru")
    try:
        head = format_hvac(rep).splitlines()[5]
    finally:
        i18n.set_active_language(None)
    assert "БазаВыходные" not in head
    for word in ("Месяц", "Всего", "База", "Выходные", "Охлажд", "Нагрев", "Прочее"):
        assert word in head
