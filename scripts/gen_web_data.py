"""Generate web/tariffs-data.js from data/tariffs.json + data/benchmarks.json (single source of truth)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
tariffs = json.loads((root / "data" / "tariffs.json").read_text(encoding="utf-8"))
benchmarks = json.loads((root / "data" / "benchmarks.json").read_text(encoding="utf-8"))
out = (
    "// GENERATED from data/tariffs.json and data/benchmarks.json by scripts/gen_web_data.py - do not edit by hand\n"
    "export const TARIFFS = " + json.dumps(tariffs, ensure_ascii=False, indent=2) + ";\n"
    "export const BENCHMARKS = " + json.dumps(benchmarks, ensure_ascii=False, indent=2) + ";\n"
)
(root / "web" / "tariffs-data.js").write_text(out, encoding="utf-8")
print(f"wrote web/tariffs-data.js ({len(out)} bytes)")
