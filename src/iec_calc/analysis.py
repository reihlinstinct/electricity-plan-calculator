"""Consumption statistics from interval data."""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .parser import Interval
from .tariffs import FRI_SAT

log = logging.getLogger(__name__)

NIGHT_START, NIGHT_END = 23, 7  # 23:00-07:00


@dataclass(frozen=True)
class Summary:
    days: int
    total_kwh: float
    avg_daily_kwh: float
    annualized_kwh: float
    base_load_kw: float  # mean 02:00-05:00 continuous draw
    peak_interval_kwh: float
    peak_interval_at: str
    peak_interval_kw: float
    night_share: float  # fraction of kWh 23:00-07:00
    fri_sat_share: float
    weekday_avg: float
    fri_sat_avg: float
    daily: dict  # date -> kWh
    hourly: list  # 24 avg kWh per hour of day
    anomaly_days: tuple  # dates with kWh > mean + 2*std


def summarize(intervals: list[Interval]) -> Summary:
    daily: dict[date, float] = defaultdict(float)
    hourly = [0.0] * 24
    for iv in intervals:
        daily[iv.start.date()] += iv.kwh
        hourly[iv.start.hour] += iv.kwh
    days = len(daily)
    total = sum(daily.values())
    night = sum(i.kwh for i in intervals if i.start.hour >= NIGHT_START or i.start.hour < NIGHT_END)
    fri_sat = {d: v for d, v in daily.items() if d.weekday() in FRI_SAT}
    weekday = {d: v for d, v in daily.items() if d.weekday() not in FRI_SAT}
    base = [i.kwh for i in intervals if 2 <= i.start.hour < 5]
    vals = list(daily.values())
    mean, std = statistics.mean(vals), statistics.pstdev(vals)
    anomalies = tuple(sorted(d for d, v in daily.items() if v > mean + 2 * std))
    peak = max(intervals, key=lambda i: i.kwh)
    interval_hours = _interval_hours(intervals)
    summary = Summary(
        days=days,
        total_kwh=total,
        avg_daily_kwh=total / days,
        annualized_kwh=total / days * 365,
        base_load_kw=statistics.mean(base) / interval_hours if base else 0.0,
        peak_interval_kwh=peak.kwh,
        peak_interval_at=peak.start.isoformat(),
        peak_interval_kw=peak.kwh / interval_hours,
        night_share=night / total if total else 0.0,
        fri_sat_share=sum(fri_sat.values()) / total if total else 0.0,
        weekday_avg=sum(weekday.values()) / len(weekday) if weekday else 0.0,
        fri_sat_avg=sum(fri_sat.values()) / len(fri_sat) if fri_sat else 0.0,
        daily=dict(sorted(daily.items())),
        hourly=[h / days for h in hourly],
        anomaly_days=anomalies,
    )
    log.debug(
        "summary: %d days, %.1f kWh, base %.3f kW, peak %.2f kW, night %.1f%%, fri/sat %.1f%%",
        days,
        total,
        summary.base_load_kw,
        summary.peak_interval_kw,
        100 * summary.night_share,
        100 * summary.fri_sat_share,
    )
    return summary


def _interval_hours(intervals: list[Interval]) -> float:
    if len(intervals) < 2:
        return 0.25
    deltas = [
        (b.start - a.start).total_seconds() / 3600
        for a, b in zip(intervals, intervals[1:], strict=False)
        if a.start.date() == b.start.date()
    ]
    return statistics.median(deltas) if deltas else 0.25
