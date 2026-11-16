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


DEFAULT_COOLING_BASE = 22.0  # deg C: above this, cooling degree-days accrue
DEFAULT_HEATING_BASE = 18.0  # deg C: below this, heating degree-days accrue


@dataclass(frozen=True)
class MonthAttribution:
    month: str  # YYYY-MM
    days: int
    total_kwh: float
    base_kwh: float
    weekend_kwh: float
    cooling_kwh: float
    heating_kwh: float
    residual_kwh: float


@dataclass(frozen=True)
class HvacReport:
    days: int
    kwh_per_cooling_degree: float | None  # None when too little cooling variance to fit
    kwh_per_heating_degree: float | None  # None when too little heating variance to fit
    r_squared: float
    cooling_base: float
    heating_base: float
    monthly: tuple[MonthAttribution, ...]


@dataclass(frozen=True)
class WeatherReport:
    days: int
    correlation: float  # Pearson r, daily kWh vs daily mean temp
    kwh_per_degree: float  # OLS slope with weekend covariate
    weekend_extra_kwh: float  # OLS weekend coefficient
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


def ols(rows: list[list[float]], y: list[float]) -> tuple[list[float], float]:
    """OLS of y on design rows [1, x1, x2, ...]; returns (coefficients, r_squared).

    Gaussian elimination with partial pivoting; raises ValueError on a
    (near-)singular design matrix.
    """
    n = len(rows[0])
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
    pred = [sum(c * x for c, x in zip(bvec, r, strict=False)) for r in rows]
    mean = statistics.mean(y)
    ss_tot = sum((yy - mean) ** 2 for yy in y)
    ss_res = sum((yy - pp) ** 2 for yy, pp in zip(y, pred, strict=False))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return bvec, r2


def ols3(x1: list[float], x2: list[float], y: list[float]) -> tuple[float, float, float, float]:
    """OLS of y on [1, x1, x2]; returns (intercept, b1, b2, r_squared)."""
    coef, r2 = ols([[1.0, a, b] for a, b in zip(x1, x2, strict=False)], y)
    return coef[0], coef[1], coef[2], r2


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
        report.correlation,
        report.kwh_per_degree,
        report.weekend_extra_kwh,
        report.r_squared,
    )
    return report


def hvac_split(
    daily_kwh: dict[date, float],
    temps: dict[date, float],
    cooling_base: float = DEFAULT_COOLING_BASE,
    heating_base: float = DEFAULT_HEATING_BASE,
) -> HvacReport | None:
    """Separate cooling from heating load via degree-days, with per-month attribution.

    Fits daily kWh ~ intercept + weekend + b_cool*CDD + b_heat*HDD where
    CDD = max(0, T - cooling_base) and HDD = max(0, heating_base - T).
    Returns None (with a debug log) when there is too little variance to fit.
    """
    common = sorted(set(daily_kwh) & set(temps))
    if len(common) < 7:
        log.debug("hvac: only %d overlapping days, skipping", len(common))
        return None
    cdd = {d: max(0.0, temps[d] - cooling_base) for d in common}
    hdd = {d: max(0.0, heating_base - temps[d]) for d in common}
    cdd_var = statistics.pstdev([cdd[d] for d in common]) >= 0.2
    hdd_var = statistics.pstdev([hdd[d] for d in common]) >= 0.2
    if not cdd_var and not hdd_var:
        log.debug("hvac: no degree-day variance in period, skipping")
        return None
    if not cdd_var:
        log.debug("hvac: too little cooling variance, fitting heating only")
    if not hdd_var:
        log.debug("hvac: too little heating variance, fitting cooling only")
    weekend = [1.0 if d.weekday() in FRI_SAT else 0.0 for d in common]
    ys = [daily_kwh[d] for d in common]
    rows = []
    for d, w in zip(common, weekend, strict=False):
        row = [1.0, w]
        if cdd_var:
            row.append(cdd[d])
        if hdd_var:
            row.append(hdd[d])
        rows.append(row)
    try:
        coef, r2 = ols(rows, ys)
    except ValueError:
        log.debug("hvac: singular design matrix, skipping")
        return None
    b0, b_weekend = coef[0], coef[1]
    i = 2
    b_cool = coef[i] if cdd_var else None
    i += 1 if cdd_var else 0
    b_heat = coef[i] if hdd_var else None
    by_month: dict[str, list[date]] = {}
    for d in common:
        by_month.setdefault(d.strftime("%Y-%m"), []).append(d)
    monthly = []
    for m in sorted(by_month):
        days = by_month[m]
        total = sum(daily_kwh[d] for d in days)
        base = b0 * len(days)
        wknd = b_weekend * sum(1.0 for d in days if d.weekday() in FRI_SAT)
        cool = (b_cool or 0.0) * sum(cdd[d] for d in days)
        heat = (b_heat or 0.0) * sum(hdd[d] for d in days)
        monthly.append(MonthAttribution(m, len(days), total, base, wknd, cool, heat, total - base - wknd - cool - heat))
    report = HvacReport(
        days=len(common),
        kwh_per_cooling_degree=b_cool,
        kwh_per_heating_degree=b_heat,
        r_squared=r2,
        cooling_base=cooling_base,
        heating_base=heating_base,
        monthly=tuple(monthly),
    )
    log.debug(
        "hvac: %s kWh/CDD, %s kWh/HDD, R2=%.2f",
        f"{b_cool:.2f}" if b_cool is not None else "n/a",
        f"{b_heat:.2f}" if b_heat is not None else "n/a",
        r2,
    )
    return report
