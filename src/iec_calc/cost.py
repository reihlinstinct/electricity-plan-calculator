"""Interval-exact plan cost computation and ranking."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .parser import Interval
from .tariffs import Catalog, SupplierPlan


@dataclass(frozen=True)
class Customer:
    """Eligibility facts that decide which supplier plans are on the table.

    Defaults include every plan; CLI flags narrow them down.
    """

    smart_meter: bool = True
    gas_customer: bool = False
    hot_customer: bool = False


def plan_available(plan: SupplierPlan, customer: Customer) -> bool:
    if plan.meter == "smart" and not customer.smart_meter:
        return False
    if plan.requires_gas_customer and not customer.gas_customer:
        return False
    return not plan.requires_hot_customer or customer.hot_customer


DEFAULT_CUSTOMER = Customer()

log = logging.getLogger(__name__)

FLAT_LABEL = 'חברת החשמל - תעריף אחיד מפוקח'
TAOZ_LABEL = 'תעו"ז מפוקח (מונה חכם)'


@dataclass(frozen=True)
class PlanCost:
    label: str
    kind: str  # "flat" | "taoz" | "supplier"
    period_cost: float
    annual_cost: float
    savings_vs_flat_annual: float
    detail: str = ""


def _annualize(period_cost: float, days: int) -> float:
    return period_cost / days * 365


def flat_cost(intervals: list[Interval], rate: float) -> float:
    return sum(i.kwh for i in intervals) * rate


def supplier_cost(intervals: list[Interval], plan: SupplierPlan, flat_rate: float) -> float:
    return sum(
        i.kwh * flat_rate * (1 - plan.discount if plan.applies(i.start) else 1)
        for i in intervals
    )


def taoz_cost(intervals: list[Interval], catalog: Catalog) -> float:
    return sum(i.kwh * catalog.taoz.rate(i.start) for i in intervals)


def unavailable_plans(catalog: Catalog, customer: Customer) -> list[SupplierPlan]:
    return [p for p in catalog.plans if not plan_available(p, customer)]


def rank_plans(
    intervals: list[Interval],
    catalog: Catalog,
    days: int,
    phase: str = "single",
    customer: Customer = DEFAULT_CUSTOMER,
) -> list[PlanCost]:
    """Annual cost (energy + fixed fees, incl. VAT) per plan, cheapest first.

    Fixed fees are identical for the flat tariff and supplier plans; Taoz's
    fixed fee is higher (schedule 5.4-1), so it is included explicitly.
    Plans failing the customer's eligibility flags are excluded.
    """
    iec_fixed = catalog.fixed_fee_annual(phase)
    taoz_fixed = catalog.fixed_fee_annual(phase, taoz=True)
    log.debug("fixed fees annual incl VAT: iec=%.0f taoz=%.0f", iec_fixed, taoz_fixed)
    base = flat_cost(intervals, catalog.flat_rate)
    flat_annual = _annualize(base, days) + iec_fixed
    out = [
        PlanCost(
            label=FLAT_LABEL,
            kind="flat",
            period_cost=base,
            annual_cost=flat_annual,
            savings_vs_flat_annual=0.0,
            detail=f"{catalog.flat_rate:.4f} NIS/kWh, all hours, fixed fee {iec_fixed:.0f} NIS/yr",
        ),
    ]
    tc = taoz_cost(intervals, catalog)
    taoz_annual = _annualize(tc, days) + taoz_fixed
    out.append(
        PlanCost(
            label=TAOZ_LABEL,
            kind="taoz",
            period_cost=tc,
            annual_cost=taoz_annual,
            savings_vs_flat_annual=flat_annual - taoz_annual,
            detail=(
                "season x peak/off-peak + higher fixed fee "
                f"{taoz_fixed:.0f} NIS/yr (vs {iec_fixed:.0f})"
            ),
        ),
    )
    for plan in catalog.plans:
        if not plan_available(plan, customer):
            log.debug("plan %s excluded by eligibility flags", plan.label)
            continue
        c = supplier_cost(intervals, plan, catalog.flat_rate)
        out.append(
            PlanCost(
                label=plan.label,
                kind="supplier",
                period_cost=c,
                annual_cost=_annualize(c, days) + iec_fixed,
                savings_vs_flat_annual=flat_annual - (_annualize(c, days) + iec_fixed),
                detail=f"{plan.discount:.1%} off, {plan.meter} meter, verified {plan.verified}",
            )
        )
    out.sort(key=lambda pc: pc.annual_cost)
    for pc in out:
        log.debug("plan %-45s annual %.0f NIS", pc.label, pc.annual_cost)
    return out
