from datetime import datetime

from iec_calc.cost import flat_cost, rank_plans, supplier_cost, taoz_cost
from iec_calc.tariffs import load_catalog


def test_flat_cost(two_days):
    total = sum(i.kwh for i in two_days)
    assert flat_cost(two_days, 0.6352) == total * 0.6352


def test_supplier_cost_flat_discount(two_days):
    cat = load_catalog()
    plan = next(p for p in cat.plans if p.window is None and p.discount == 0.065)
    c = supplier_cost(two_days, plan, cat.flat_rate)
    assert abs(c - flat_cost(two_days, cat.flat_rate) * (1 - 0.065)) < 1e-9


def test_supplier_cost_night_window(two_days):
    cat = load_catalog()
    # Cellcom night plan: 15% off 23:00-07:00 every day
    plan = next(p for p in cat.plans if p.window and p.window.start == 23 * 60 and p.window.days == "all")
    night_kwh = sum(i.kwh for i in two_days if i.start.hour >= 23 or i.start.hour < 7)
    total = sum(i.kwh for i in two_days)
    expected = (total - night_kwh) * cat.flat_rate + night_kwh * cat.flat_rate * 0.85
    assert abs(supplier_cost(two_days, plan, cat.flat_rate) - expected) < 1e-9


def test_taoz_cost_transition(two_days):
    # both days are October: Sunday = transition peak 17-22, Friday all off-peak
    cat = load_catalog()
    sunday = datetime(2026, 10, 4).date()
    sun_peak = sum(i.kwh for i in two_days if i.start.date() == sunday and 17 <= i.start.hour < 22)
    sun_off = sum(i.kwh for i in two_days if i.start.date() == sunday and not 17 <= i.start.hour < 22)
    fri = sum(i.kwh for i in two_days if i.start.date() == datetime(2026, 10, 9).date())
    expected = sun_peak * 0.4958 + (sun_off + fri) * 0.4578
    assert abs(taoz_cost(two_days, cat) - expected) < 1e-9


def test_ranking_sorted_and_marks_recommendation(two_days):
    cat = load_catalog()
    ranked = rank_plans(two_days, cat, days=2)
    assert ranked == sorted(ranked, key=lambda c: c.annual_cost)
    assert len(ranked) == 20  # 18 unconditional supplier plans + flat + taoz (gas/HOT opt-in)
    flat = next(c for c in ranked if c.kind == "flat")
    assert flat.savings_vs_flat_annual == 0.0
    best = ranked[0]
    assert best.annual_cost <= flat.annual_cost
    assert best.savings_vs_flat_annual >= 0


def test_ranking_includes_fixed_fees(two_days):
    cat = load_catalog()
    ranked = rank_plans(two_days, cat, days=2)
    by_kind = {c.kind: c for c in ranked}
    iec_fixed = 25.57 * 12 * 1.18
    taoz_fixed = 47.63 * 12 * 1.18
    assert abs(by_kind["flat"].annual_cost - (flat_cost(two_days, cat.flat_rate) / 2 * 365 + iec_fixed)) < 0.01
    taoz_energy = taoz_cost(two_days, cat) / 2 * 365
    assert abs(by_kind["taoz"].annual_cost - (taoz_energy + taoz_fixed)) < 0.01
    # Taoz's higher fixed fee erases part of its energy saving
    assert by_kind["taoz"].savings_vs_flat_annual < (by_kind["flat"].annual_cost - taoz_energy)
    assert "fixed fee" in by_kind["taoz"].detail


def test_ranking_three_phase(two_days):
    cat = load_catalog()
    ranked3 = rank_plans(two_days, cat, days=2, phase="three")
    flat3 = next(c for c in ranked3 if c.kind == "flat")
    assert abs(flat3.annual_cost - (flat_cost(two_days, cat.flat_rate) / 2 * 365 + 27.09 * 12 * 1.18)) < 0.01
