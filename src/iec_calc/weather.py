"""Weather sensitivity: correlate daily consumption with daily temperature.

Data source: Open-Meteo archive API (free, no key). Network access is
isolated in fetch_daily_temps() so tests never touch the network.
"""
from __future__ import annotations

import json
import logging
import statistics
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from .tariffs import FRI_SAT

log = logging.getLogger(__name__)

API = "https://archive-api.open-meteo.com/v1/archive"


@dataclass(frozen=True)
class WeatherReport:
    days: int
    correlation: float          # Pearson r, daily kWh vs daily mean temp
    kwh_per_degree: float       # OLS slope with weekend covariate
    weekend_extra_kwh: float    # OLS weekend coefficient
    r_squared: float
    temp_min: float
    temp_max: float


def fetch_daily_temps(
    lat: float,
    lon: float,
    start: date,
    end: date,
    opener: Callable = urllib.request.urlopen,
) -> dict[date, float]:
    """Return {date: mean temperature} from Open-Meteo. opener is injectable for tests."""
    url = (
        f"{API}?latitude={lat}&longitude={lon}&start_date={start.isoformat()}"
        f"&end_date={end.isoformat()}&daily=temperature_2m_mean&timezone=auto"
    )
    log.debug("weather fetch: %s", url)
    with opener(url, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    days = payload["daily"]["time"]
    temps = payload["daily"]["temperature_2m_mean"]
    return {date.fromisoformat(d): t for d, t in zip(days, temps, strict=False) if t is not None}


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False)) / len(xs)
    sx, sy = statistics.pstdev(xs), statistics.pstdev(ys)
    return cov / (sx * sy) if sx and sy else 0.0


def ols3(x1: list[float], x2: list[float], y: list[float]) -> tuple[float, float, float, float]:
    """OLS of y on [1, x1, x2]; returns (intercept, b1, b2, r_squared)."""
    n = 3
    rows = [[1.0, a, b] for a, b in zip(x1, x2, strict=False)]
    amat = [[sum(r[i] * r[j] for r in rows) for j in range(n)] for i in range(n)]
    bvec = [sum(r[i] * yy for r, yy in zip(rows, y, strict=False)) for i in range(n)]
    for i in range(n):
        piv_row = max(range(i, n), key=lambda r: abs(amat[r][i]))
        if abs(amat[piv_row][i]) < 1e-12:
            raise ValueError("singular design matrix")
        amat[i], amat[piv_row] = amat[piv_row], amat[i]
        bvec[i], bvec[piv_row] = bvec[piv_row], bvec[i]
        piv = amat[i][i]
        for j in range(i, n):
            amat[i][j] /= piv
        bvec[i] /= piv
        for k in range(n):
            if k != i:
                factor = amat[k][i]
                for j in range(i, n):
                    amat[k][j] -= factor * amat[i][j]
                bvec[k] -= factor * bvec[i]
    pred = [bvec[0] + bvec[1] * a + bvec[2] * b for a, b in zip(x1, x2, strict=False)]
    mean = statistics.mean(y)
    ss_tot = sum((yy - mean) ** 2 for yy in y)
    ss_res = sum((yy - pp) ** 2 for yy, pp in zip(y, pred, strict=False))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return bvec[0], bvec[1], bvec[2], r2


def sensitivity(
    daily_kwh: dict[date, float],
    temps: dict[date, float],
) -> WeatherReport | None:
    common = sorted(set(daily_kwh) & set(temps))
    if len(common) < 7:
        log.debug("weather: only %d overlapping days, skipping", len(common))
        return None
    ys = [daily_kwh[d] for d in common]
    ts = [temps[d] for d in common]
    if statistics.pstdev(ts) < 1.0:
        log.debug("weather: temperature variance too low (pstdev < 1C), slope meaningless, skipping")
        return None
    weekend = [1.0 if d.weekday() in FRI_SAT else 0.0 for d in common]
    try:
        _, b_weekend, b_temp, r2 = ols3(weekend, ts, ys)
    except ValueError:
        log.debug("weather: singular design matrix (constant inputs?), skipping")
        return None
    report = WeatherReport(
        days=len(common),
        correlation=pearson(ts, ys),
        kwh_per_degree=b_temp,
        weekend_extra_kwh=b_weekend,
        r_squared=r2,
        temp_min=min(ts),
        temp_max=max(ts),
    )
    log.debug(
        "weather: r=%.3f, %.2f kWh/deg, weekend +%.2f kWh, R2=%.2f",
        report.correlation, report.kwh_per_degree, report.weekend_extra_kwh, report.r_squared,
    )
    return report
