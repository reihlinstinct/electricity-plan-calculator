from datetime import date, datetime

from iec_calc.tariffs import Window, is_workday, load_catalog

SUNDAY = datetime(2026, 10, 4, 12, 0)   # workday
FRIDAY = datetime(2026, 10, 9, 12, 0)   # weekend
SATURDAY = datetime(2026, 10, 10, 12, 0)


def test_is_workday():
    assert is_workday(date(2026, 10, 4))
    assert not is_workday(date(2026, 10, 9))
    assert not is_workday(date(2026, 10, 10))
    assert not is_workday(date(2026, 10, 4), holidays=frozenset({date(2026, 10, 4)}))


def test_day_window():
    w = Window(days="sun-thu", start=7 * 60, end=17 * 60)
    assert w.contains(SUNDAY.replace(hour=10))
    assert not w.contains(SUNDAY.replace(hour=18))
    assert not w.contains(FRIDAY.replace(hour=10))
    assert not w.contains(SUNDAY.replace(hour=6))


def test_night_window_wraps_midnight():
    w = Window(days="sun-thu", start=23 * 60, end=7 * 60)
    assert w.contains(SUNDAY.replace(hour=23, minute=30))        # Sunday night start
    assert w.contains(datetime(2026, 10, 5, 2, 0))               # Monday 02:00 (night of Sunday)
    assert not w.contains(FRIDAY.replace(hour=23, minute=30))    # Friday night excluded
    assert not w.contains(SUNDAY.replace(hour=2))                # Saturday night excluded
    assert not w.contains(SUNDAY.replace(hour=8))


def test_full_day_window_all_days():
    w = Window(days="all", start=0, end=0)
    assert w.contains(SUNDAY) and w.contains(SATURDAY)


def test_catalog_loads():
    cat = load_catalog()
    assert cat.flat_rate == 0.6352
    assert len(cat.plans) == 20
    assert all(p.source.startswith("http") and p.verified for p in cat.plans)
    assert cat.retrieved == "2026-11-02"


def test_taoz_rates():
    cat = load_catalog()
    tz = cat.taoz
    # summer weekday 18:00 = peak, 23:30 = off, Friday 18:00 = off
    assert tz.rate(datetime(2026, 7, 5, 18, 0)) == 1.7223
    assert tz.rate(datetime(2026, 7, 5, 23, 30)) == 0.5042
    assert tz.rate(datetime(2026, 7, 10, 18, 0)) == 0.5042
    # winter: peak every day incl Saturday, 17-22
    assert tz.rate(datetime(2026, 1, 10, 18, 0)) == 1.1470   # Saturday
    assert tz.rate(datetime(2026, 1, 11, 22, 30)) == 0.4663
    # transition weekday peak 17-22 only
    assert tz.rate(datetime(2026, 10, 4, 18, 0)) == 0.4958
    assert tz.rate(datetime(2026, 10, 4, 22, 30)) == 0.4578
    assert tz.rate(datetime(2026, 10, 9, 18, 0)) == 0.4578   # Friday
    # holiday = off-peak
    tz_h = type(tz)(seasons=tz.seasons, holidays=frozenset({date(2026, 10, 4)}))
    assert tz_h.rate(datetime(2026, 10, 4, 18, 0)) == 0.4578


def test_fixed_fee_annual_amounts():
    cat = load_catalog()
    assert abs(cat.fixed_fee_annual() - 25.57 * 12 * 1.18) < 0.01
    assert abs(cat.fixed_fee_annual(phase="three") - 27.09 * 12 * 1.18) < 0.01
    assert abs(cat.fixed_fee_annual(taoz=True) - 47.63 * 12 * 1.18) < 0.01


def test_holiday_data_loaded():
    cat = load_catalog()
    assert len(cat.taoz.holidays) >= 14
    assert len(cat.taoz.holiday_eves) >= 14
    assert date(2026, 9, 12) in cat.taoz.holidays  # Rosh Hashana day 1
    assert date(2026, 9, 21) in cat.taoz.holidays  # Yom Kippur
    assert date(2026, 9, 20) in cat.taoz.holiday_eves


def test_winter_peak_on_holiday():
    # winter peak applies every day, holidays included (schedule 5.1-1, decision 63609)
    cat = load_catalog()
    tz = type(cat.taoz)(
        seasons=cat.taoz.seasons,
        holidays=frozenset({date(2027, 1, 15)}),
        holiday_eves=cat.taoz.holiday_eves,
        fixed_fee_monthly_pre_vat=cat.taoz.fixed_fee_monthly_pre_vat,
    )
    assert tz.rate(datetime(2027, 1, 15, 18, 0)) == 1.1470  # Friday in winter, holiday
