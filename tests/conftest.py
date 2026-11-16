import sys
from datetime import date, datetime, time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iec_calc.parser import Interval  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_consumption.csv"


@pytest.fixture(scope="session")
def sample_csv() -> Path:
    return SAMPLE


@pytest.fixture()
def two_days() -> list[Interval]:
    """Two synthetic days: Sunday (workday) and Friday (weekend), 15-min slots."""
    out = []
    for d in (date(2026, 10, 4), date(2026, 10, 9)):  # Sunday, Friday
        for slot in range(96):
            hh, mm = divmod(slot * 15, 60)
            kwh = 0.05
            if 17 <= hh < 22:
                kwh = 0.20
            out.append(Interval(datetime.combine(d, time(hh, mm)), kwh))
    return out
