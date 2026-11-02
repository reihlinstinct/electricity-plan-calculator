import io
import json
from datetime import date, timedelta

from iec_calc.weather import fetch_daily_temps, ols3, pearson, sensitivity


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
