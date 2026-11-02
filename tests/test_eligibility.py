"""Eligibility filter flags (#10)."""
from datetime import datetime, timedelta

from iec_calc.cost import Customer, plan_available, rank_plans, unavailable_plans
from iec_calc.parser import Interval
from iec_calc.tariffs import load_catalog


def _intervals():
    start = datetime(2026, 10, 4)
    return [Interval(start + timedelta(minutes=15 * i), 0.1, 0.0) for i in range(96)]


def _plans_by_supplier(cat, name):
    return [p for p in cat.plans if name in p.supplier]


def test_gas_only_plan_filtered():
    cat = load_catalog()
    amisragas = _plans_by_supplier(cat, "אמישראגז")
    assert amisragas
    assert all(not plan_available(p, Customer(gas_customer=False)) for p in amisragas)
    assert all(plan_available(p, Customer(gas_customer=True)) for p in amisragas)


def test_smart_meter_plans_filtered():
    cat = load_catalog()
    smart = [p for p in cat.plans if p.meter == "smart"]
    assert smart
    assert all(not plan_available(p, Customer(smart_meter=False)) for p in smart)
    assert all(plan_available(p, Customer(smart_meter=True)) for p in smart)


def test_rank_plans_filters_and_reports_excluded():
    cat = load_catalog()
    intervals = _intervals()
    customer = Customer(smart_meter=False, gas_customer=False, hot_customer=False)
    ranked = rank_plans(intervals, cat, days=1, customer=customer)
    excluded = unavailable_plans(cat, customer)
    assert len(ranked) + len(excluded) == 22
    labels = [c.label for c in ranked]
    assert not any("אמישראגז" in lbl for lbl in labels)


def test_default_customer_excludes_conditional_plans_by_default():
    cat = load_catalog()
    ranked = rank_plans(_intervals(), cat, days=1)
    assert len(ranked) == 20
    excluded = unavailable_plans(cat, Customer())
    assert len(excluded) == 2


def test_eligibility_flags_come_from_data_not_text():
    # review follow-up: no substring matching on the eligibility text
    cat = load_catalog()
    flagged = [p for p in cat.plans if p.requires_gas_customer or p.requires_hot_customer]
    assert flagged, "data should carry explicit requirement flags"
    for p in flagged:
        assert not plan_available(p, Customer(gas_customer=False, hot_customer=False))


def test_default_customer_excludes_conditional_plans():
    cat = load_catalog()
    ranked = rank_plans(_intervals(), cat, days=1, customer=Customer())
    labels = [p.label for p in ranked]
    assert not any("אמישראגז" in lbl for lbl in labels)
    assert "HOT energy - חוסכים קבוע" not in labels  # other HOT energy plans need no membership
    excluded = unavailable_plans(cat, Customer())
    assert any("אמישראגז" in p.label for p in excluded)
    assert any(p.label == "HOT energy - חוסכים קבוע" for p in excluded)
    assert len(ranked) + len(excluded) == 22
