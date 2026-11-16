"""Translations loader - i18n/strings.json is the single source of truth.

The catalog is also the only place that names languages: each one is a block
under "languages" (keyed by its code: own name, dir, default, machine_draft,
optional locale). The CLI renders in the catalog's default language unless
--lang picks another; nothing here lists language codes.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from .resources import resource_path

STRINGS_PATH = resource_path("strings.json")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=1)
def _doc() -> dict:
    return json.loads(STRINGS_PATH.read_text(encoding="utf-8"))


def default_lang() -> str:
    for code, meta in _doc()["languages"].items():
        if meta.get("default"):
            return code
    return next(iter(_doc()["languages"]))


def languages() -> dict:
    return _doc()["languages"]


_active_lang: str | None = None


def set_active_language(lang: str) -> None:
    """Set the process-wide language used by t() when lang is None (CLI --lang)."""
    global _active_lang
    _active_lang = lang if lang in languages() else None


def t(key: str, lang: str | None = None, **params: object) -> str:
    """Render a string key in lang (default: the file's default language).

    Falls back to the default language for a missing translation, then to the
    key itself. Unknown placeholders are left as-is, so a template mismatch
    is visible rather than fatal.
    """
    entry = _doc()["strings"].get(key)
    if entry is None:
        return key
    lang = lang or _active_lang or default_lang()
    template = entry.get(lang) or entry.get(default_lang())
    if template is None:
        return key
    return _PLACEHOLDER.sub(lambda m: str(params.get(m.group(1), m.group(0))), template)
