"""Text report rendering (Hebrew-friendly plain text)."""

from __future__ import annotations

from .analysis import Summary
from .cost import PlanCost
from .i18n import t as _t
from .insights import InsightsReport
from .resources import resource_path
from .tariffs import Catalog
from .weather import HvacReport, WeatherReport


def _nis(v: float) -> str:
    return f"{v:,.0f} ₪"


def format_analysis(s: Summary) -> str:
    lines = [
        _t("report.analysis_title"),
        "===========",
        _t("report.period", days=s.days, total=f"{s.total_kwh:.1f}", avg=f"{s.avg_daily_kwh:.2f}"),
        _t("report.annual_est", kwh=f"{s.annualized_kwh:,.0f}"),
        _t("report.base_line", watts=f"{s.base_load_kw * 1000:.0f}"),
        _t("report.peak_line", kw=f"{s.peak_interval_kw:.2f}", at=s.peak_interval_at),
        _t("report.night_weekend", night=f"{s.night_share:.1%}", weekend=f"{s.fri_sat_share:.1%}"),
        _t("report.weekday_avg", weekday=f"{s.weekday_avg:.2f}", weekend=f"{s.fri_sat_avg:.2f}"),
    ]
    if s.anomaly_days:
        lines.append(_t("report.anomaly_days", days=", ".join(str(d) for d in s.anomaly_days)))
    return "\n".join(lines)


def format_weather(w: WeatherReport) -> str:
    return "\n".join(
        [
            _t("report.weather_title"),
            "=================",
            _t(
                "report.weather_corr",
                r=f"{w.correlation:.2f}",
                tmin=f"{w.temp_min:.0f}",
                tmax=f"{w.temp_max:.0f}",
                days=w.days,
            ),
            _t("report.weather_sens", sens=f"{w.kwh_per_degree:+.2f}", wknd=f"{w.weekend_extra_kwh:+.2f}"),
            _t("report.model_r2", r2=f"{w.r_squared:.2f}"),
        ]
    )


def format_ranking(
    costs: list[PlanCost],
    days: int,
    catalog: Catalog,
    excluded: list | None = None,
    current_label: str | None = None,
) -> str:
    lines = [
        _t("report.ranking_title"),
        "====================================================",
    ]
    current = None
    if current_label:
        current = next((c for c in costs if current_label in c.label), None)
    for i, c in enumerate(costs, 1):
        marker = _t("report.best_marker") if i == 1 else ""
        if current is not None and c.label == current.label:
            marker = _t("report.best_current_marker") if i == 1 else _t("report.current_marker")
        lines.append(
            f"{i:2d}. {c.label:<48} {_nis(c.annual_cost):>9} | "
            f"{_t('report.savings_word')} {_nis(c.savings_vs_flat_annual):>7}{marker}"
        )
    lines += [
        "",
        _t("report.compare_base", rate=f"{catalog.flat_rate:.4f}", days=days),
        _t("report.costs_include_fixed"),
        _t("report.taoz_fixed_higher", fee=f"{catalog.taoz.fixed_fee_monthly_pre_vat:.2f}"),
        _t("report.smart_meter_required"),
    ]
    if current is not None:
        best = costs[0]
        delta = current.annual_cost - best.annual_cost
        lines += [
            "",
            _t("report.current_plan_line", label=current.label, cost=_nis(current.annual_cost)),
        ]
        if current.label == best.label:
            lines.append(_t("report.current_is_best"))
        else:
            lines.append(_t("report.switch_saves", best=best.label, amount=_nis(delta)))
    elif current_label:
        lines += [
            "",
            _t("report.current_excluded", label=current_label),
        ]
    if excluded:
        lines += ["", _t("report.excluded_header")]
        lines += [f"  - {p.label} ({p.eligibility})" for p in excluded]
    return lines_to_text(lines)


def lines_to_text(lines: list[str]) -> str:
    return "\n".join(lines)


def format_hvac(h: HvacReport) -> str:
    lines = [
        _t("report.hvac_title"),
        "=============================",
        (
            _t("report.hvac_cooling", v=f"{h.kwh_per_cooling_degree:+.2f}", base=f"{h.cooling_base:.0f}")
            if h.kwh_per_cooling_degree is not None
            else _t("report.hvac_cooling_na")
        )
        + " | "
        + (
            _t("report.hvac_heating", v=f"{h.kwh_per_heating_degree:+.2f}", base=f"{h.heating_base:.0f}")
            if h.kwh_per_heating_degree is not None
            else _t("report.hvac_heating_na")
        ),
        _t("report.hvac_r2", r2=f"{h.r_squared:.2f}", days=h.days),
        "",
        _t("report.hvac_table_head"),
    ]
    for m in h.monthly:
        cells = [m.total_kwh, m.base_kwh, m.weekend_kwh, m.cooling_kwh, m.heating_kwh, m.residual_kwh]
        # round-off can leave a tiny negative that renders as "-0"; snap to 0
        cells = [0.0 if round(v) == 0 else v for v in cells]
        lines.append(f"{m.month:<9}" + "".join(f"{v:>8.0f}" for v in cells))
    return lines_to_text(lines)


_KIND_KEYS = {
    "washing_machine": "app.kind_washing_machine",
    "oven": "app.kind_oven",
    "sustained_high": "app.kind_sustained_high",
}
_CONF_KEYS = {"high": "app.confidence_high", "medium": "app.confidence_medium", "low": "app.confidence_low"}


def format_insights(rep: InsightsReport, flat_rate: float) -> str:
    """Observations only - every line is descriptive of the file, never causal."""
    lines = [
        _t("report.insights_title"),
        "=========================================",
    ]
    span = f"{rep.first:%d.%m.%Y} - {rep.last:%d.%m.%Y}"
    if not rep.covers_full_year:
        lines.append(_t("report.coverage_partial", days=rep.days, span=span))
    else:
        lines.append(_t("report.coverage_full", days=rep.days, span=span))
    hours = ", ".join(f"{h:02d}:00 ({v:.2f})" for h, v in rep.peak_hours)
    lines.append(_t("report.peak_hours_line", hours=hours))
    lines.append(_t("report.weekday_avg", weekday=f"{rep.weekday_avg:.2f}", weekend=f"{rep.weekend_avg:.2f}"))
    base_annual_nis = rep.night_base_kw * 24 * 365 * flat_rate
    lines.append(_t("report.base_floor_line", watts=f"{rep.night_base_kw * 1000:.0f}", nis=f"{base_annual_nis:,.0f}"))
    if rep.shabbat_count:
        lines.append(
            _t(
                "app.shabbat_line",
                count=rep.shabbat_count,
                avg=f"{rep.shabbat_avg_kwh:.1f}",
                shabbat=f"{rep.shabbat_night_base_kw * 1000:.0f}",
                base=f"{rep.night_base_kw * 1000:.0f}",
            )
        )
    ob = rep.observance
    if ob is not None:
        pct = round((ob.base_ratio - 1) * 100)
        base_txt = _t("app.obs_base", pct=pct)
        appl_txt = _t("app.obs_appl", starts=ob.shabbat_starts, count=ob.shabbat_count, rate=f"{ob.weekday_rate:.1f}")
        if ob.confidence == "high":
            detail = base_txt + _t("app.obs_join") + appl_txt
        elif "base" in ob.signals:
            detail = base_txt + _t("app.obs_base_note")
        else:
            detail = appl_txt
        level = _t("app.level_high") if ob.confidence == "high" else _t("app.level_medium")
        lead = _t("app.obs_lead_high") if ob.confidence == "high" else _t("app.obs_lead_medium")
        lines.append(_t("app.obs_line", lead=lead, level=level, detail=detail))
    if rep.notable_days:
        days = ", ".join(f"{d:%d.%m}" for d in rep.notable_days)
        lines.append(_t("app.notable_days", days=days))
    lines.append(_t("app.taoz_peak", kwh=f"{rep.taoz_peak_kwh:.0f}", pct=f"{rep.taoz_peak_cost_share * 100:.0f}"))
    if rep.appliances:
        lines.append("")
        lines.append(_t("app.appliances_header"))
        by_kind: dict[str, list] = {}
        for a in rep.appliances:
            by_kind.setdefault(a.kind, []).append(a)
        for kind, key in _KIND_KEYS.items():
            events = by_kind.get(kind)
            if not events:
                continue
            confs = {}
            for e in events:
                confs[e.confidence] = confs.get(e.confidence, 0) + 1
            conf_txt = ", ".join(
                _t("app.appliance_conf_part", n=n, conf=_t(_CONF_KEYS[c])) for c, n in sorted(confs.items())
            )
            lines.append("- " + _t("app.appliance_line", label=_t(key), count=len(events), confs=conf_txt))
            for e in sorted(events, key=lambda x: x.excess_kwh, reverse=True)[:2]:
                day_name = _t(f"app.day_{(e.start.weekday() + 1) % 7}")
                lines.append(
                    "  "
                    + _t(
                        "app.appliance_example",
                        day=day_name,
                        date=f"{e.start:%d.%m}",
                        start=f"{e.start:%H:%M}",
                        end=f"{e.end:%H:%M}",
                        kwh=f"{e.excess_kwh:.1f}",
                        conf=_t(_CONF_KEYS[e.confidence]),
                        pattern=e.pattern,
                    )
                )
    if rep.efficiency:
        lines.append("")
        lines.append(_t("app.eff_header"))
        for n in rep.efficiency:
            cost = _t("app.eff_annual", nis=f"{n.annual_nis:,.0f}") if n.annual_nis is not None else ""
            lines.append(f"- {n.text} ({_t(_CONF_KEYS[n.confidence])}).{cost}")
        lines.append(_t("report.eff_sources", path=str(resource_path("benchmarks.json"))))
    return lines_to_text(lines)
