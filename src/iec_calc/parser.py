"""Tolerant parser for Israel Electric Corp consumption CSV exports.

The export is UTF-8 with BOM, Hebrew metadata header (customer name, address,
contract number, meter number) followed by interval rows:

    "00-00000001","צריכה","01/10/2026","00:15",0.041,0

Privacy: customer metadata is never returned or logged; only interval data.
"""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_METER_CODE = re.compile(r"^\d+-\d+$")
_DATE_FMT = "%d/%m/%Y"
CONSUMPTION_KIND = "צריכה"


@dataclass(frozen=True)
class Interval:
    """One metered interval (15 minutes or 1 hour)."""

    start: datetime
    kwh: float
    feed_kwh: float = 0.0


def parse(path: str | Path) -> list[Interval]:
    """Parse an IEC export and return consumption intervals, sorted by start.

    Raises ValueError if no consumption rows are found.
    """
    p = Path(path)
    intervals: list[Interval] = []
    skipped = 0
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for raw in csv.reader(fh):
            cells = [c.strip().strip('"') for c in raw]
            if len(cells) < 5 or not _METER_CODE.match(cells[0]):
                skipped += 1
                continue
            try:
                day = datetime.strptime(cells[2], _DATE_FMT).date()
                hour, minute = (int(x) for x in cells[3].split(":"))
                kwh = float(cells[4] or 0)
                feed = float(cells[5]) if len(cells) > 5 and cells[5] else 0.0
            except ValueError:
                skipped += 1
                log.debug("skipping malformed row of %d cells", len(raw))
                continue
            if cells[1] != CONSUMPTION_KIND:
                skipped += 1
                continue
            if hour == 24 and minute == 0:  # exports may write midnight as 24:00
                start = datetime.combine(day, time(0, 0)) + timedelta(days=1)
            elif 0 <= hour < 24 and 0 <= minute < 60:
                start = datetime.combine(day, time(hour, minute))
            else:
                skipped += 1
                log.debug("skipping row with invalid interval time")
                continue
            intervals.append(Interval(start, kwh, feed))
    intervals.sort(key=lambda i: i.start)
    log.debug(
        "parsed %d intervals (%d rows skipped), range %s..%s",
        len(intervals),
        skipped,
        intervals[0].start if intervals else "n/a",
        intervals[-1].start if intervals else "n/a",
    )
    if not intervals:
        raise ValueError(f"no consumption intervals found in {p}")
    return intervals
