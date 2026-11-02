"""Insights: descriptive stats and appliance-signature detection on synthetic data."""
from datetime import date, datetime, timedelta

from iec_calc.analysis import summarize
from iec_calc.insights import FULL_YEAR_DAYS, build_insights, detect_appliances
from iec_calc.parser import Interval
from iec_calc.tariffs import load_catalog


def _day_intervals(d: date, base_kw: float = 0.2) -> list[Interval]:
    return [
        Interval(datetime(d.year, d.month, d.day) + timedelta(hours=h, minutes=m), base_kw * 0.25, 0.0)
        for h in range(24) for m in (0, 15, 30, 45)
    ]


def _add_block(ivs: list[Interval], d: date, hour: float, quarter_hours: list[float]) -> None:
    """Overwrite quarter-hours from `hour` with the given kW levels."""
    start = int(hour * 4)
    for i, kw in enumerate(quarter_hours):
        idx = start + i
        ivs[idx] = Interval(ivs[idx].start, kw * 0.25, 0.0)


def test_washing_machine_signature():
    d = date(2026, 10, 5)  # Monday
    ivs = _day_intervals(d)
    # 45 min motor (0.4 kW), 30 min water heating (2.0 kW), 30 min motor, 15 min spin (0.6)
    _add_block(ivs, d, 10, [0.4, 0.4, 0.4, 2.0, 2.0, 0.4, 0.4, 0.6])
    events = detect_appliances(ivs, 0.2)
    assert len(events) == 1
    e = events[0]
    assert e.kind == "washing_machine"
    assert e.confidence == "high"
    assert "חימום מים" in e.pattern
    assert (e.end - e.start).total_seconds() == 8 * 900  # 10:00-12:00: end of last interval


def test_oven_signature():
    d = date(2026, 10, 6)
    ivs = _day_intervals(d)
    # thermostat cycling: 2.2 kW on / 0.3 kW off, 4 transitions over 60 min
    _add_block(ivs, d, 18, [2.2, 0.3, 2.2, 0.3, 2.2, 0.3, 2.2, 0.3])
    events = detect_appliances(ivs, 0.2)
    assert len(events) == 1
    assert events[0].kind == "oven"
    assert events[0].confidence == "medium"


def test_sustained_high_type_unclear():
    d = date(2026, 10, 7)
    ivs = _day_intervals(d)
    _add_block(ivs, d, 19, [1.2] * 8)  # 2 hours steady 1.2 kW
    events = detect_appliances(ivs, 0.2)
    assert len(events) == 1
    assert events[0].kind == "sustained_high"
    assert events[0].confidence == "low"


def test_flat_day_no_events():
    ivs = _day_intervals(date(2026, 10, 8))
    assert detect_appliances(ivs, 0.2) == ()


def test_daylong_block_not_an_appliance():
    d = date(2026, 10, 9)
    ivs = _day_intervals(d)
    _add_block(ivs, d, 7, [1.0] * 64)  # 16 hours: daytime activity, not one appliance
    assert detect_appliances(ivs, 0.2) == ()


def test_coverage_flag_and_fields():
    cat = load_catalog()
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(10)]
    ivs = [iv for d in days for iv in _day_intervals(d)]
    s = summarize(ivs)
    rep = build_insights(ivs, s, cat)
    assert rep.covers_full_year is False
    assert rep.days == 10
    assert len(rep.peak_hours) == 3
    assert rep.taoz_peak_kwh > 0

    ivs_year = [
        iv
        for i in range(FULL_YEAR_DAYS + 1)
        for iv in _day_intervals(date(2026, 1, 1) + timedelta(days=i))
    ]
    s_year = summarize(ivs_year)
    rep_year = build_insights(ivs_year, s_year, cat)
    assert rep_year.covers_full_year is True


def test_format_insights_observational_language():
    from iec_calc.report import format_insights
    cat = load_catalog()
    d = date(2026, 10, 5)
    ivs = _day_intervals(d)
    _add_block(ivs, d, 10, [0.4, 0.4, 0.4, 2.0, 2.0, 0.4, 0.4, 0.6])
    s = summarize(ivs)
    rep = build_insights(ivs, s, cat)
    text = format_insights(rep, cat.flat_rate)
    assert "אין להסיק" in text  # coverage warning
    assert "הסתברותית" in text and "לא ודאות" in text
    assert "מכונת כביסה אפשרית" in text
    assert "יום שני" in text
    assert "עומס בסיס" in text


def test_sunset_approximation_reasonable():
    from iec_calc.insights import sunset_local_minutes
    # Jerusalem mid-October: ~18:10 IDT; mid-January ~16:55; mid-July ~19:45
    assert 17.8 * 60 < sunset_local_minutes(date(2026, 10, 15), 31.78, 35.21) < 18.5 * 60
    assert 16.5 * 60 < sunset_local_minutes(date(2026, 1, 15), 31.78, 35.21) < 17.3 * 60
    assert 19.3 * 60 < sunset_local_minutes(date(2026, 7, 15), 31.78, 35.21) < 20.1 * 60


def test_shabbat_baseline_separation():
    from iec_calc.insights import build_insights
    cat = load_catalog()
    ivs = []
    d0 = date(2026, 10, 5)  # Monday
    for i in range(14):
        d = d0 + timedelta(days=i)
        base = 0.45 if d.weekday() == 5 or (d.weekday() == 4) else 0.2  # Shabbat+Friday raised
        ivs += _day_intervals(d, base)
    s = summarize(ivs)
    rep = build_insights(ivs, s, cat)
    assert rep.night_base_kw < 0.25  # weekday nights only
    assert rep.shabbat_night_base_kw > 0.4
    assert rep.shabbat_count >= 1


def test_no_appliance_false_positive_from_shabbat_plate():
    from iec_calc.insights import build_insights
    cat = load_catalog()
    ivs = []
    d0 = date(2026, 10, 5)
    for i in range(14):
        d = d0 + timedelta(days=i)
        ivs += _day_intervals(d, 0.45 if d.weekday() == 5 else 0.2)
    s = summarize(ivs)
    rep = build_insights(ivs, s, cat)
    assert rep.appliances == ()
