"""Descriptive insights from the IEC export only.

Every statement is an observation over the file ("בשעות 18-22 הצריכה גבוהה"),
never a causal claim. Appliance detection reports a probabilistic likelihood
from 15-minute load signatures, with the triggering pattern spelled out.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import date, datetime

from .analysis import Summary
from .parser import Interval
from .tariffs import Catalog

log = logging.getLogger(__name__)

FULL_YEAR_DAYS = 350  # below this, warn against seasonal comparison

# appliance-signature thresholds (excess kW over the night baseline)
MIN_EXCESS_KW = 0.15        # block membership
HIGH_KW = 1.2               # resistive-heating interval
WASHER_MIN_MIN, WASHER_MAX_MIN = 45, 180
OVEN_MIN_MIN, OVEN_MAX_MIN = 20, 150
SUSTAINED_MIN_MIN = 45
SUSTAINED_MAX_MIN = 360  # longer blocks are daytime activity, not one appliance
SUSTAINED_MIN_MEAN_KW = 0.8


@dataclass(frozen=True)
class ApplianceEvent:
    kind: str  # "washing_machine" | "oven" | "sustained_high"
    confidence: str  # "high" | "medium" | "low"
    start: datetime
    end: datetime
    excess_kwh: float
    pattern: str  # the signature that triggered the classification


@dataclass(frozen=True)
class InsightsReport:
    days: int
    first: date
    last: date
    covers_full_year: bool
    peak_hours: tuple[tuple[int, float], ...]  # top 3 (hour, avg kWh per interval)
    weekday_avg: float
    weekend_avg: float
    night_base_kw: float
    notable_days: tuple[date, ...]
    taoz_peak_kwh: float
    taoz_peak_cost_share: float
    appliances: tuple[ApplianceEvent, ...]


def _interval_hours(intervals: list[Interval]) -> float:
    deltas = [
        (b.start - a.start).total_seconds()
        for a, b in zip(intervals, intervals[1:], strict=False)
        if 0 < (b.start - a.start).total_seconds() <= 3600
    ]
    return (statistics.median(deltas) if deltas else 900) / 3600


def detect_appliances(intervals: list[Interval], base_kw: float) -> tuple[ApplianceEvent, ...]:
    """Classify elevated-load blocks by their 15-minute load signature.

    Washing machine: a 45-180 min block with >=2 consecutive resistive-heating
    intervals (>=1.2 kW over baseline) plus sustained low motor activity.
    Oven: 20-150 min with thermostat on/off cycling (>=3 high/low transitions).
    Sustained high: anything else >=45 min averaging >=0.8 kW over baseline -
    reported as "type unclear" (AC / electric heater / boiler cannot be told
    apart from consumption alone).
    """
    hours = _interval_hours(intervals)
    events: list[ApplianceEvent] = []
    # blocks of excess > MIN_EXCESS_KW, merging across single-interval dips
    blocks: list[list[int]] = []
    i = 0
    n = len(intervals)
    ex = [iv.kwh / hours - base_kw for iv in intervals]
    while i < n:
        if ex[i] > MIN_EXCESS_KW:
            j = i
            while j + 1 < n and (ex[j + 1] > MIN_EXCESS_KW or (j + 2 < n and ex[j + 2] > MIN_EXCESS_KW)):
                j += 1 if ex[j + 1] > MIN_EXCESS_KW else 2
            blocks.append(list(range(i, j + 1)))
            i = j + 1
        else:
            i += 1
    for idxs in blocks:
        exs = [ex[k] for k in idxs]
        dur_min = len(idxs) * hours * 60
        energy = sum(e * hours for e in exs)
        start, end = intervals[idxs[0]].start, intervals[idxs[-1]].start
        hi = [e >= HIGH_KW for e in exs]
        max_consec_hi = 0
        run = 0
        for h in hi:
            run = run + 1 if h else 0
            max_consec_hi = max(max_consec_hi, run)
        transitions = sum(
            1 for a, b in zip(exs, exs[1:], strict=False)
            if (a >= HIGH_KW) != (b >= HIGH_KW) and min(a, b) < 0.6
        )
        if (
            WASHER_MIN_MIN <= dur_min <= WASHER_MAX_MIN
            and max_consec_hi >= 2
            and sum(1 for e in exs if MIN_EXCESS_KW < e < HIGH_KW) >= 3
            and 0.4 <= energy <= 2.5
        ):
            conf = "high" if max(exs) >= 1.5 and energy >= 0.6 else "medium"
            events.append(ApplianceEvent(
                "washing_machine", conf, start, end, round(energy, 2),
                f"בלוק {dur_min:.0f} דק' עם {max_consec_hi} רבעי-שעה רצופים ~{max(exs):.1f} קילוואט"
                " (חימום מים) + פעילות מתונה (מנוע)",
            ))
        elif OVEN_MIN_MIN <= dur_min <= OVEN_MAX_MIN and max(exs) >= 1.5 and transitions >= 3:
            events.append(ApplianceEvent(
                "oven", "medium", start, end, round(energy, 2),
                f"בלוק {dur_min:.0f} דק' עם {transitions} מעברי דלוק/כבוי (תרמוסטט) ושיא ~{max(exs):.1f} קילוואט",
            ))
        elif (
            SUSTAINED_MIN_MIN <= dur_min <= SUSTAINED_MAX_MIN
            and statistics.mean(exs) >= SUSTAINED_MIN_MEAN_KW
        ):
            events.append(ApplianceEvent(
                "sustained_high", "low", start, end, round(energy, 2),
                f"עומס רציף ~{statistics.mean(exs):.1f} קילוואט למשך {dur_min:.0f} דק'",
            ))
        else:
            log.debug("unclassified block at %s (%d intervals, %.2f kWh)", start, len(idxs), energy)
    return tuple(events)


def build_insights(intervals: list[Interval], summary: Summary, catalog: Catalog) -> InsightsReport:
    """Descriptive observations over the file; no weather, no inference beyond the CSV."""
    ordered = sorted(intervals, key=lambda i: i.start)
    days = sorted(summary.daily)
    peak_hours = tuple(sorted(enumerate(summary.hourly), key=lambda kv: kv[1], reverse=True)[:3])
    peak_kwh = sum(i.kwh for i in ordered if catalog.taoz.is_peak(i.start))
    peak_cost = sum(i.kwh * catalog.taoz.rate(i.start) for i in ordered if catalog.taoz.is_peak(i.start))
    total_cost = sum(i.kwh * catalog.taoz.rate(i.start) for i in ordered)
    appliances = detect_appliances(ordered, summary.base_load_kw)
    log.debug("insights: %d days, %d appliance candidates", len(days), len(appliances))
    return InsightsReport(
        days=len(days),
        first=days[0],
        last=days[-1],
        covers_full_year=len(days) >= FULL_YEAR_DAYS,
        peak_hours=peak_hours,
        weekday_avg=summary.weekday_avg,
        weekend_avg=summary.fri_sat_avg,
        night_base_kw=summary.base_load_kw,
        notable_days=summary.anomaly_days,
        taoz_peak_kwh=peak_kwh,
        taoz_peak_cost_share=peak_cost / total_cost if total_cost else 0.0,
        appliances=appliances,
    )
