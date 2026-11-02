"""Descriptive insights from the IEC export only.

Every statement is an observation over the file ("בשעות 18-22 הצריכה גבוהה"),
never a causal claim. Appliance detection reports a probabilistic likelihood
from 15-minute load signatures, with the triggering pattern spelled out.
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .analysis import FRI_SAT, Summary
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

# Shabbat-observance detection thresholds (statistics only, never a negative claim)
OBS_MIN_SHABBATOT = 2        # need at least this many Shabbat windows
OBS_MIN_WEEKDAYS = 5         # and this many weekdays for a meaningful rate
OBS_BASE_MIN_DELTA_KW = 0.05 # absolute Shabbat-night elevation over weekday-night base
OBS_BASE_RATIO = 1.3         # and at least 30% higher
OBS_WEEKDAY_MIN_RATE = 0.15  # appliance starts per weekday: household uses appliances at all
OBS_SHABBAT_MAX_SHARE = 0.25 # Shabbat start rate at most this share of the weekday rate


def _israel_utc_offset(d: date) -> int:
    """+3 during IDT (Friday before the last Sunday of March .. last Sunday of October), else +2."""

    def last_sunday(month: int) -> date:
        d_ = date(d.year, month + 1, 1) - timedelta(days=1) if month < 12 else date(d.year, 12, 31)
        while d_.weekday() != 6:
            d_ -= timedelta(days=1)
        return d_

    end = last_sunday(10)
    start = last_sunday(3) - timedelta(days=2)  # the Friday before
    return 3 if start <= d < end else 2


def sunset_local_minutes(d: date, lat: float, lon: float) -> float:
    """NOAA solar approximation of sunset, in local clock minutes. No network."""
    g = 2 * math.pi / 365 * (d.timetuple().tm_yday - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    latr = math.radians(lat)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(decl))
              - math.tan(latr) * math.tan(decl))
    ha = math.degrees(math.acos(min(1.0, max(-1.0, cos_ha))))
    utc = 720 - 4 * (lon - ha) - eqtime  # solar noon + hour angle
    return utc + 60 * _israel_utc_offset(d)


def shabbat_window(saturday: date, lat: float, lon: float) -> tuple[datetime, datetime]:
    """Friday sunset to Saturday nightfall (~42 min after sunset)."""
    friday = saturday - timedelta(days=1)
    start = datetime.combine(friday, time()) + timedelta(minutes=sunset_local_minutes(friday, lat, lon))
    end = datetime.combine(saturday, time()) + timedelta(minutes=sunset_local_minutes(saturday, lat, lon) + 42)
    return start, end


@dataclass(frozen=True)
class ApplianceEvent:
    kind: str  # "washing_machine" | "oven" | "sustained_high"
    confidence: str  # "high" | "medium" | "low"
    start: datetime
    end: datetime
    excess_kwh: float
    pattern: str  # the signature that triggered the classification


@dataclass(frozen=True)
class ObservanceReport:
    """Statistical Shabbat-observance estimate; never a negative conclusion."""

    confidence: str  # "high" (both signals) | "medium" (one)
    signals: tuple[str, ...]  # subset of ("base", "appliances")
    base_ratio: float  # shabbat_night_base / night_base (0 when night_base is 0)
    shabbat_starts: int  # appliance events starting inside Shabbat windows
    shabbat_count: int
    weekday_rate: float  # appliance starts per weekday


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
    shabbat_count: int  # distinct Shabbat windows overlapping the data
    shabbat_avg_kwh: float  # mean kWh per Shabbat window
    shabbat_night_base_kw: float  # mean 02:00-05:00 draw on Shabbat nights
    observance: ObservanceReport | None = None  # None = below threshold, stay neutral


def _interval_hours(intervals: list[Interval]) -> float:
    deltas = [
        (b.start - a.start).total_seconds()
        for a, b in zip(intervals, intervals[1:], strict=False)
        if 0 < (b.start - a.start).total_seconds() <= 3600
    ]
    return (statistics.median(deltas) if deltas else 900) / 3600


def detect_shabbat_observance(
    *,
    shabbat_count: int,
    weekday_days: int,
    night_base_kw: float,
    shabbat_night_base_kw: float,
    shabbat_starts: int,
    weekday_starts: int,
) -> ObservanceReport | None:
    """Estimate likely Shabbat observance from two local statistics.

    Signal "base": Shabbat-night base elevated over weekday-night base
    (plate/urn signature). Signal "appliances": near-absence of appliance
    starts inside Shabbat windows while weekdays show normal use. Returns
    None below the combined threshold - the caller stays neutral and never
    reports non-observance.
    """
    if shabbat_count < OBS_MIN_SHABBATOT or weekday_days < OBS_MIN_WEEKDAYS:
        return None
    signals: list[str] = []
    base_ratio = shabbat_night_base_kw / night_base_kw if night_base_kw > 0 else 0.0
    if (
        night_base_kw > 0
        and shabbat_night_base_kw - night_base_kw >= OBS_BASE_MIN_DELTA_KW
        and base_ratio >= OBS_BASE_RATIO
    ):
        signals.append("base")
    weekday_rate = weekday_starts / weekday_days
    if weekday_rate >= OBS_WEEKDAY_MIN_RATE and shabbat_starts / shabbat_count <= OBS_SHABBAT_MAX_SHARE * weekday_rate:
        signals.append("appliances")
    if not signals:
        return None
    return ObservanceReport(
        confidence="high" if len(signals) == 2 else "medium",
        signals=tuple(signals),
        base_ratio=base_ratio,
        shabbat_starts=shabbat_starts,
        shabbat_count=shabbat_count,
        weekday_rate=weekday_rate,
    )


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
        start = intervals[idxs[0]].start
        end = intervals[idxs[-1]].start + timedelta(seconds=hours * 3600)
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


def build_insights(
    intervals: list[Interval],
    summary: Summary,
    catalog: Catalog,
    lat: float = 31.78,
    lon: float = 35.21,
) -> InsightsReport:
    """Descriptive observations over the file; no weather, no inference beyond the CSV.

    Shabbat-aware: the night baseline and appliance detection use non-Shabbat
    nights only (a plate/urn legitimately raises the Shabbat baseline), and
    Shabbat (Friday sunset to Saturday nightfall) gets its own averages.
    """
    ordered = sorted(intervals, key=lambda i: i.start)
    days = sorted(summary.daily)
    saturdays = sorted({(d + timedelta(days=(5 - d.weekday()) % 7)) for d in days})
    windows = [shabbat_window(sat, lat, lon) for sat in saturdays]

    def in_shabbat(dt: datetime) -> bool:
        return any(a <= dt < b for a, b in windows)

    non_shabbat_night = [
        i.kwh for i in ordered if 2 <= i.start.hour < 5 and not in_shabbat(i.start)
    ]
    shabbat_night = [i.kwh for i in ordered if 2 <= i.start.hour < 5 and in_shabbat(i.start)]
    hours = _interval_hours(ordered)
    base_kw = statistics.mean(non_shabbat_night) / hours if non_shabbat_night else summary.base_load_kw
    shabbat_kwh: dict[int, float] = {}
    for i in ordered:
        for n, (a, b) in enumerate(windows):
            if a <= i.start < b:
                shabbat_kwh[n] = shabbat_kwh.get(n, 0.0) + i.kwh
                break
    peak_hours = tuple(sorted(enumerate(summary.hourly), key=lambda kv: kv[1], reverse=True)[:3])
    peak_kwh = sum(i.kwh for i in ordered if catalog.taoz.is_peak(i.start))
    peak_cost = sum(i.kwh * catalog.taoz.rate(i.start) for i in ordered if catalog.taoz.is_peak(i.start))
    total_cost = sum(i.kwh * catalog.taoz.rate(i.start) for i in ordered)
    appliances = detect_appliances(ordered, base_kw)
    shabbat_starts = sum(1 for a in appliances if in_shabbat(a.start))
    weekday_days = sum(1 for d in days if d.weekday() not in FRI_SAT)
    observance = detect_shabbat_observance(
        shabbat_count=len(shabbat_kwh),
        weekday_days=weekday_days,
        night_base_kw=base_kw,
        shabbat_night_base_kw=(
            statistics.mean(shabbat_night) / hours if shabbat_night else 0.0
        ),
        shabbat_starts=shabbat_starts,
        weekday_starts=len(appliances) - shabbat_starts,
    )
    log.debug("insights: %d days, %d appliance candidates", len(days), len(appliances))
    return InsightsReport(
        days=len(days),
        first=days[0],
        last=days[-1],
        covers_full_year=len(days) >= FULL_YEAR_DAYS,
        peak_hours=peak_hours,
        weekday_avg=summary.weekday_avg,
        weekend_avg=summary.fri_sat_avg,
        night_base_kw=base_kw,
        notable_days=summary.anomaly_days,
        taoz_peak_kwh=peak_kwh,
        taoz_peak_cost_share=peak_cost / total_cost if total_cost else 0.0,
        appliances=appliances,
        shabbat_count=len(shabbat_kwh),
        shabbat_avg_kwh=statistics.mean(shabbat_kwh.values()) if shabbat_kwh else 0.0,
        shabbat_night_base_kw=(statistics.mean(shabbat_night) / hours) if shabbat_night else 0.0,
        observance=observance,
    )
