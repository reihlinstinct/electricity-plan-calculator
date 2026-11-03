import io
import json
from datetime import date, timedelta

from iec_calc.weather import fetch_daily_temps, hvac_split, ols3, pearson, sensitivity


def test_pearson():
    assert abs(pearson([1, 2, 3, 4], [2, 4, 6, 8]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3, 4], [8, 6, 4, 2]) + 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0
    assert pearson([1], [2]) == 0.0


def test_ols3_recovers_coefficients():
    xs1 = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    xs2 = [20, 21, 22, 19, 23, 24, 18, 25, 21, 20]
    ys = [3 + 2 * a + 0.5 * b for a, b in zip(xs1, xs2, strict=False)]
    b0, b1, b2, r2 = ols3(xs1, xs2, ys)
    assert abs(b0 - 3) < 1e-9 and abs(b1 - 2) < 1e-9 and abs(b2 - 0.5) < 1e-9
    assert abs(r2 - 1) < 1e-9


def test_fetch_parses_response():
    payload = {
        "daily": {
            "time": ["2026-10-01", "2026-10-02"],
            "temperature_2m_mean": [21.5, None],
        }
    }

    def fake_opener(url, timeout):
        assert "latitude=31.78" in url
        return io.BytesIO(json.dumps(payload).encode())

    class Ctx:
        def __enter__(self):
            return io.BytesIO(json.dumps(payload).encode())

        def __exit__(self, *a):
            return False

    temps = fetch_daily_temps(31.78, 35.21, date(2026, 10, 1), date(2026, 10, 2), opener=lambda url, timeout: Ctx())
    assert temps == {date(2026, 10, 1): 21.5}


def test_sensitivity_needs_overlap():
    assert sensitivity({date(2026, 10, 1): 5.0}, {}) is None


def test_sensitivity_math():
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(14)]
    temps = {d: 20 + (i % 5) for i, d in enumerate(days)}
    kwh = {d: 6 + 0.3 * (20 + (i % 5)) + (3.0 if d.weekday() in (4, 5) else 0) for i, d in enumerate(days)}
    w = sensitivity(kwh, temps)
    assert w is not None and w.days == 14
    assert abs(w.kwh_per_degree - 0.3) < 1e-6
    assert abs(w.weekend_extra_kwh - 3.0) < 1e-6
    assert w.r_squared > 0.99
    assert w.temp_min == 20 and w.temp_max == 24


def test_sensitivity_singular_returns_none():
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(10)]
    temps = {d: 20.0 for d in days}  # constant -> singular
    kwh = {d: 6.0 for d in days}
    assert sensitivity(kwh, temps) is None


def test_low_temperature_variance_returns_none():
    # near-constant temps: any slope would be noise, report nothing (#8 follow-up)
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(14)]
    temps = {d: 25.3 for d in days}
    kwh = {d: 6.0 + (i % 3) for i, d in enumerate(days)}
    assert sensitivity(kwh, temps) is None


def _synthetic_hvac_days():
    # 60 days: known coefficients b0=5, weekend=+3, cool=0.8/CDD, heat=1.2/HDD
    days = [date(2026, 9, 1) + timedelta(days=i) for i in range(60)]
    temps, kwh = {}, {}
    for i, d in enumerate(days):
        t = 20.0 + 8.0 * ((i * 7) % 13) / 13 - (4.0 if i > 40 else 0.0)
        temps[d] = t
        kwh[d] = 5.0 + (3.0 if d.weekday() in (4, 5) else 0.0) + 0.8 * max(0.0, t - 22.0) + 1.2 * max(0.0, 18.0 - t)
    return kwh, temps


def test_hvac_split_recovers_coefficients():
    kwh, temps = _synthetic_hvac_days()
    rep = hvac_split(kwh, temps)
    assert rep is not None
    assert abs(rep.kwh_per_cooling_degree - 0.8) < 0.05
    assert abs(rep.kwh_per_heating_degree - 1.2) < 0.05
    assert rep.r_squared > 0.99


def test_hvac_monthly_attribution_sums():
    kwh, temps = _synthetic_hvac_days()
    rep = hvac_split(kwh, temps)
    assert [m.month for m in rep.monthly] == ["2026-09", "2026-10"]
    for m in rep.monthly:
        attributed = m.base_kwh + m.weekend_kwh + m.cooling_kwh + m.heating_kwh
        assert abs(attributed + m.residual_kwh - m.total_kwh) < 1e-6
    sep = rep.monthly[0]
    assert sep.cooling_kwh > 0


def test_hvac_split_none_without_variance():
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(10)]
    temps = {d: 20.0 for d in days}  # between the bases: no CDD/HDD at all
    kwh = {d: 6.0 + (i % 2) for i, d in enumerate(days)}
    assert hvac_split(kwh, temps) is None


def test_hvac_single_sided_variance():
    # only cooling variance: heating coefficient is None, cooling still fitted
    kwh, temps = _synthetic_hvac_days()
    temps = {d: max(t, 20.0) for d, t in temps.items()}  # never below 18
    rep = hvac_split(kwh, temps)
    assert rep is not None
    assert rep.kwh_per_heating_degree is None
    assert rep.kwh_per_cooling_degree is not None


def test_hvac_report_render():
    from iec_calc.report import format_hvac

    kwh, temps = _synthetic_hvac_days()
    text = format_hvac(hvac_split(kwh, temps))
    assert "קירור" in text and "חימום" in text and "שאר" in text
    assert "2026-09" in text


def test_hvac_report_render_one_sided():
    from iec_calc.report import format_hvac

    kwh, temps = _synthetic_hvac_days()
    temps = {d: max(t, 20.0) for d, t in temps.items()}
    text = format_hvac(hvac_split(kwh, temps))
    assert "אין מספיק שונות" in text


def test_hvac_debug_log_one_sided_no_crash(caplog):
    # regression: the final debug log used %.2f with a None regressor -> TypeError
    import logging

    kwh, temps = _synthetic_hvac_days()
    temps = {d: max(t, 20.0) for d, t in temps.items()}  # heating-only fit
    with caplog.at_level(logging.DEBUG, logger="iec_calc.weather"):
        rep = hvac_split(kwh, temps)
    assert rep is not None and rep.kwh_per_heating_degree is None
    assert "n/a" in caplog.text


def test_hvac_report_no_negative_zero():
    from iec_calc.report import format_hvac
    from iec_calc.weather import HvacReport, MonthAttribution

    rep = HvacReport(
        days=30,
        kwh_per_cooling_degree=1.0,
        kwh_per_heating_degree=None,
        r_squared=0.5,
        cooling_base=22.0,
        heating_base=18.0,
        monthly=(MonthAttribution("2026-09", 30, 300.0, 180.0, 40.0, 60.5, 20.0, -0.5),),
    )
    text = format_hvac(rep)
    assert "-0" not in text.split("2026-09", 1)[1]


def test_collinear_weather_regressors_skip_fit(caplog):
    # Temperature varies by 10C, bypassing the low-variance guard, but is an
    # exact linear combination of the intercept and Fri/Sat indicator.
    import logging

    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(14)]
    temps = {d: 20.0 + 10.0 * (d.weekday() in (4, 5)) for d in days}
    kwh = {d: 6.0 + i for i, d in enumerate(days)}
    with caplog.at_level(logging.DEBUG, logger="iec_calc.weather"):
        assert sensitivity(kwh, temps) is None
    assert "singular design matrix" in caplog.text
    assert "temperature variance too low" not in caplog.text
