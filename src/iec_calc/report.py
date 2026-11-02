"""Text report rendering (Hebrew-friendly plain text)."""
from __future__ import annotations

from .analysis import Summary
from .cost import PlanCost
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


def format_ranking(costs: list[PlanCost], days: int, flat_rate: float) -> str:
    lines = [
        'דירוג מסלולים (עלות שנתית משוערת: צריכה + תשלומים קבועים, כולל מע"מ)',
        "====================================================",
    ]
    for i, c in enumerate(costs, 1):
        marker = "  <<< הכי משתלם" if i == 1 else ""
        lines.append(
            f"{i:2d}. {c.label:<48} {_nis(c.annual_cost):>9} | "
            f"חיסכון {_nis(c.savings_vs_flat_annual):>7}{marker}"
        )
    lines += [
        "",
        f"בסיס ההשוואה: תעריף אחיד {flat_rate:.4f} ₪/קוט\"ש כולל מע\"מ; {days} ימי מדידה, הוכפל לשנה.",
        "העלויות כוללות את התשלומים הקבועים (כולל מע\"מ).",
        'בתעו"ז התשלום הקבוע גבוה יותר (47.63 ₪/חודש לפני מע"מ). מסלולי שעות דורשים מונה חכם.',
    ]
    return lines_to_text(lines)


def lines_to_text(lines: list[str]) -> str:
    return "\n".join(lines)
