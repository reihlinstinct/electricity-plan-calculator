"""Regenerate the language lists in README.md and man/iec-calc.1 from i18n/strings.json.

The catalog is the only language source: each doc keeps its list between
"languages:begin" and "languages:end" marker lines, and this script rewrites
what is between them. `--check` exits 1 when a doc is stale (used by tests).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFT = "machine draft, pending native-speaker review"


def languages() -> dict:
    return json.loads((ROOT / "i18n" / "strings.json").read_text(encoding="utf-8"))["languages"]


def readme_block(langs: dict) -> list[str]:
    lines = []
    for code, meta in langs.items():
        notes = ["default"] if meta.get("default") else []
        if meta.get("machine_draft"):
            notes.append(DRAFT)
        lines.append(f"- `{code}` {meta['name']}" + (f" ({'; '.join(notes)})" if notes else ""))
    return lines


def man_block(langs: dict) -> list[str]:
    items = [f"{code} (default)" if meta.get("default") else code for code, meta in langs.items()]
    listed = ", ".join(items[:-1]) + (", or " if len(items) > 1 else "") + items[-1]
    return [f"Output language: {listed}."]


TARGETS = {
    "README.md": (re.compile(r"^<!-- languages:begin\b.*-->$"), re.compile(r"^<!-- languages:end -->$"), readme_block),
    "man/iec-calc.1": (re.compile(r'^\.\\" languages:begin\b.*$'), re.compile(r'^\.\\" languages:end$'), man_block),
}


def render(rel: str, text: str, langs: dict) -> str:
    begin, end, block = TARGETS[rel]
    lines = text.split("\n")
    starts = [i for i, ln in enumerate(lines) if begin.match(ln)]
    ends = [i for i, ln in enumerate(lines) if end.match(ln)]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise SystemExit(f"{rel}: expected exactly one languages:begin/end marker pair")
    return "\n".join(lines[: starts[0] + 1] + block(langs) + lines[ends[0] :])


def main(argv: list[str]) -> int:
    check = "--check" in argv
    langs = languages()
    stale = []
    for rel in TARGETS:
        path = ROOT / rel
        old = path.read_text(encoding="utf-8")
        new = render(rel, old, langs)
        if new != old:
            stale.append(rel)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("language lists are stale - run scripts/gen_language_lists.py: " + ", ".join(stale))
        return 1
    if not check:
        print("language lists: " + (", ".join(stale) + " rewritten" if stale else "up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
