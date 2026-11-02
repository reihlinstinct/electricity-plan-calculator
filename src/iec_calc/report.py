"""Text report rendering (Hebrew-friendly plain text)."""
from __future__ import annotations

from .analysis import Summary
from .cost import PlanCost
from .tariffs import Catalog
from .weather import WeatherReport


def _nis(v: float) -> str:
    return f"{v:,.0f} ₪"


def format_analysis(s: Summary) -> str:
    lines = [
        "ניתוח צריכה",
        "===========",
        f'תקופה: {s.days} ימים | סה"כ {s.total_kwh:.1f} קוט"ש'
        f" | ממוצע {s.avg_daily_kwh:.2f} קוט\"ש/יום",
        f"הערכה שנתית: {s.annualized_kwh:,.0f} קוט\"ש",
        f"עומס בסיס (02:00-05:00): {s.base_load_kw * 1000:.0f} וואט",
        f"שיא: {s.peak_interval_kw:.2f} קילוואט ({s.peak_interval_at})",
        f"לילה (23:00-07:00): {s.night_share:.1%} | שישי-שבת: {s.fri_sat_share:.1%}",
        f"ממוצע יום חול: {s.weekday_avg:.2f} | ממוצע שישי-שבת: {s.fri_sat_avg:.2f} קוט\"ש",
    ]
    if s.anomaly_days:
        lines.append("ימים חריגים (מעל ממוצע + 2 סטיות תקן): " + ", ".join(str(d) for d in s.anomaly_days))
    return "\n".join(lines)


def format_weather(w: WeatherReport) -> str:
    return "\n".join(
        [
            "רגישות למזג אוויר",
            "=================",
            f"מתאם צריכה-טמפ' (יומי): r={w.correlation:.2f} "
            f"(טווח {w.temp_min:.0f}-{w.temp_max:.0f} מעלות, {w.days} ימים)",
            f"רגישות (אחרי נטרול סופ\"ש): {w.kwh_per_degree:+.2f} קוט\"ש/יום למעלה | "
            f"סופ\"ש: {w.weekend_extra_kwh:+.2f} קוט\"ש/יום",
            f"הסבר המודל: R²={w.r_squared:.2f}",
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
        'דירוג מסלולים (עלות שנתית משוערת: צריכה + תשלומים קבועים, כולל מע"מ)',
        "====================================================",
    ]
    current = None
    if current_label:
        current = next(
            (c for c in costs if current_label in c.label), None
        )
    for i, c in enumerate(costs, 1):
        marker = "  <<< הכי משתלם" if i == 1 else ""
        if current is not None and c.label == current.label:
            marker = (
                "  <<< הכי משתלם (המסלול הנוכחי שלך)" if i == 1 else "  <<< המסלול הנוכחי"
            )
        lines.append(
            f"{i:2d}. {c.label:<48} {_nis(c.annual_cost):>9} | "
            f"חיסכון {_nis(c.savings_vs_flat_annual):>7}{marker}"
        )
    lines += [
        "",
        f"בסיס ההשוואה: תעריף אחיד {catalog.flat_rate:.4f} ₪/קוט\"ש כולל מע\"מ; {days} ימי מדידה, הוכפל לשנה.",
        "העלויות כוללות את התשלומים הקבועים (כולל מע\"מ).",
        f'בתעו"ז התשלום הקבוע גבוה יותר ({catalog.taoz.fixed_fee_monthly_pre_vat:.2f} ₪/חודש לפני מע"מ).',
        "מסלולי שעות דורשים מונה חכם.",
    ]
    if current is not None:
        best = costs[0]
        delta = current.annual_cost - best.annual_cost
        lines += [
            "",
            f"המסלול הנוכחי: {current.label} ({_nis(current.annual_cost)} לשנה).",
        ]
        if current.label == best.label:
            lines.append("המסלול הנוכחי שלך הוא הזול ביותר - אין צורך להחליף.")
        else:
            lines.append(f"מעבר ל{best.label} חוסך {_nis(delta)} לשנה מול המסלול הנוכחי.")
    elif current_label:
        lines += [
            "",
            f"שים לב: המסלול הנוכחי ('{current_label}') לא נכלל בדירוג עקב דגלי הזכאות שהוגדרו.",
        ]
    if excluded:
        lines += ["", "לא נכללו בדירוג לפי דגלי הזכאות שהוגדרו:"]
        lines += [f"  - {p.label} ({p.eligibility})" for p in excluded]
    return lines_to_text(lines)


def lines_to_text(lines: list[str]) -> str:
    return "\n".join(lines)
