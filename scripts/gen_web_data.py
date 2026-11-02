"""Generate web/tariffs-data.js from data/tariffs.json (single source of truth)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.loads((root / "data" / "tariffs.json").read_text(encoding="utf-8"))
out = (
    "// GENERATED from data/tariffs.json by scripts/gen_web_data.py - do not edit by hand\n"
    "export const TARIFFS = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
)
(root / "web" / "tariffs-data.js").write_text(out, encoding="utf-8")
print(f"wrote web/tariffs-data.js ({len(out)} bytes)")
