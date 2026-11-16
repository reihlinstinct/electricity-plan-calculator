from iec_calc.analysis import summarize


def test_summary_math(two_days):
    s = summarize(two_days)
    assert s.days == 2
    assert abs(s.total_kwh - 2 * (76 * 0.05 + 20 * 0.20)) < 1e-9
    assert abs(s.avg_daily_kwh - (76 * 0.05 + 20 * 0.20)) < 1e-9
    assert abs(s.annualized_kwh - s.avg_daily_kwh * 365) < 1e-9
    # base load = 02:00-05:00 mean interval kWh / 0.25h = 0.05/0.25 = 0.2 kW
    assert abs(s.base_load_kw - 0.2) < 1e-9
    assert s.peak_interval_kwh == 0.20
    assert s.peak_interval_kw == 0.8
    # night 23-07 = 8h = 32 intervals at 0.05 per day
    night = 2 * 32 * 0.05
    assert abs(s.night_share - night / s.total_kwh) < 1e-9
    assert abs(s.fri_sat_share - 0.5) < 1e-9
    assert len(s.hourly) == 24
    assert abs(s.hourly[20] - 0.80) < 1e-9  # 4 x 15-min slots at 0.20
    assert s.weekday_avg == s.fri_sat_avg  # identical synthetic days


def test_anomaly_detection(two_days):
    s = summarize(two_days)
    assert s.anomaly_days == ()
