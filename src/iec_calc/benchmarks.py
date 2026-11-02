"""Typical-technology benchmark figures (data/benchmarks.json), with sources."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Benchmarks:
    accessed: str
    washer_typical_kwh_per_cycle: float
    ac_inverter_savings_min: float
    ac_inverter_savings_max: float
    fridge_typical_kwh_per_year: float


def load_benchmarks(path: str | Path | None = None) -> Benchmarks:
    p = Path(path) if path else Path(__file__).resolve().parents[2] / "data" / "benchmarks.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return Benchmarks(
        accessed=d["accessed"],
        washer_typical_kwh_per_cycle=d["washer"]["typical_modern_kwh_per_cycle"],
        ac_inverter_savings_min=d["ac"]["inverter_savings_min"],
        ac_inverter_savings_max=d["ac"]["inverter_savings_max"],
        fridge_typical_kwh_per_year=d["fridge"]["typical_modern_kwh_per_year"],
    )
