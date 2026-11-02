"""Text report rendering (Hebrew-friendly plain text)."""
from __future__ import annotations

from .analysis import Summary
from .cost import PlanCost
from .insights import InsightsReport
from .tariffs import Catalog
from .weather import HvacReport, WeatherReport


def _nis(v: float) -> str:
    return f"{v:,.0f} ₪"


def format_analysis(s: Summary) -> str:
    lines = [
        "ניתוח צריכה",
        "===========",
        f'תקופה: {s.days} ימים | סה"כ {s.total_kwh:.1f} קוט"ש'
        f" | ממוצע {s.avg_daily_kwh:.2f} קוט\"ש/יום",
        f"הערכה שנתית: {s.annualized_kwh:,.0f} קוט\"ש",
        f"רצפת צריכה (בסיס, 02:00-05:00): {s.base_load_kw * 1000:.0f} וואט",
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
            "רגישות למזג אוויר (אומדן ניסיוני, לא חלק מהמלצת המסלול)",
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


def format_hvac(h: HvacReport) -> str:
    lines = [
        "פיצול קירור/חימום (אומדן ניסיוני, לא חלק מהמלצת המסלול)",
        "=============================",
        (
            f"קירור: {h.kwh_per_cooling_degree:+.2f} קוט\"ש/יום לכל מעלה מעל {h.cooling_base:.0f}°"
            if h.kwh_per_cooling_degree is not None
            else "קירור: אין מספיק שונות בטמפרטורה למדידה"
        ) + " | " + (
            f"חימום: {h.kwh_per_heating_degree:+.2f} קוט\"ש/יום לכל מעלה מתחת {h.heating_base:.0f}°"
            if h.kwh_per_heating_degree is not None
            else "חימום: אין מספיק שונות בטמפרטורה למדידה"
        ),
        f"הסבר המודל: R²={h.r_squared:.2f} ({h.days} ימים)",
        "",
        "חודש     " + '  סה"כ' + "   בסיס" + '  סופ"ש' + "   קירור" + "   חימום" + "    שאר",
    ]
    for m in h.monthly:
        cells = [m.total_kwh, m.base_kwh, m.weekend_kwh, m.cooling_kwh, m.heating_kwh, m.residual_kwh]
        # round-off can leave a tiny negative that renders as "-0"; snap to 0
        cells = [0.0 if round(v) == 0 else v for v in cells]
        lines.append(
            f"{m.month:<9}" + "".join(f"{v:>8.0f}" for v in cells)
        )
    return lines_to_text(lines)

_KIND_LABELS = {
    "washing_machine": "מכונת כביסה אפשרית",
    "oven": "תנור אפייה אפשרי",
    "sustained_high": "עומס גבוה ממושך (ייתכן מזגן/חימום/דוד - לא ניתן להבחין מהצריכה בלבד)",
}
_CONF_LABELS = {"high": "ביטחון גבוה", "medium": "ביטחון בינוני", "low": "ביטחון נמוך"}
_HE_DAY = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def format_insights(rep: InsightsReport, flat_rate: float) -> str:
    """Observations only - every line is descriptive of the file, never causal."""
    lines = [
        "תובנות מהנתונים (תצפיות על הקובץ בלבד)",
        "=========================================",
    ]
    span = f"{rep.first:%d.%m.%Y} - {rep.last:%d.%m.%Y}"
    if not rep.covers_full_year:
        lines.append(
            f"כיסוי: {rep.days} ימים ({span}). השוואה עונתית (חורף/קיץ) דורשת ייצוא של שנה "
            "מלאה; אין להסיק מהקובץ על עונות שאינן בו."
        )
    else:
        lines.append(f"כיסוי: {rep.days} ימים ({span}) - שנה מלאה.")
    hours = ", ".join(f"{h:02d}:00 ({v:.2f})" for h, v in rep.peak_hours)
    lines.append(f"שעות שיא ממוצעות: {hours} קוט\"ש")
    lines.append(
        f"ממוצע יום חול: {rep.weekday_avg:.2f} | ממוצע שישי-שבת: {rep.weekend_avg:.2f} קוט\"ש"
    )
    base_annual_nis = rep.night_base_kw * 24 * 365 * flat_rate
    lines.append(
        f"רצפת צריכה (בסיס): {rep.night_base_kw * 1000:.0f} וואט"
        f" (כ-{base_annual_nis:,.0f} ₪ לשנה אם קבוע) - מקרר שעובד תמיד "
        "ועוד מכשירים מחוברים שכל אחד צורך מעט; יחד הם יוצרים את הרצפה"
    )
    if rep.shabbat_count:
        lines.append(
            f'שבת (שקיעת ו\' עד צאת השבת, {rep.shabbat_count} שבתות): ממוצע {rep.shabbat_avg_kwh:.1f} קוט"ש '
            f"לשבת; צריכת לילה {rep.shabbat_night_base_kw * 1000:.0f} וואט מול "
            f"{rep.night_base_kw * 1000:.0f} בחול - עומס קבוע (למשל פלטה/מיחם) הוא הסבר אפשרי, לא ודאי"
        )
    ob = rep.observance
    if ob is not None:
        pct = round((ob.base_ratio - 1) * 100)
        base_txt = (
            f"צריכת ליל שבת גבוהה ב-{pct}% מליל חול"
        )
        appl_txt = (
            f"{ob.shabbat_starts} הפעלות מכשירים ב-{ob.shabbat_count} שבתות "
            f"(מול {ob.weekday_rate:.1f} ליום חול בממוצע)"
        )
        if ob.confidence == "high":
            detail = base_txt + " ו" + appl_txt
        elif "base" in ob.signals:
            detail = base_txt + " - עומס קבוע כמו פלטה/מיחם הוא הסבר אפשרי"
        else:
            detail = appl_txt
        level = "גבוה" if ob.confidence == "high" else "בינוני"
        lead = "נראה" if ob.confidence == "high" else "ייתכן"
        lines.append(
            f"{lead} שבמשק הבית שומרים שבת (ביטחון {level}): {detail}. "
            "תצפית סטטיסטית מהקובץ בלבד, לא ודאות"
        )
    if rep.notable_days:
        days = ", ".join(f"{d:%d.%m}" for d in rep.notable_days)
        lines.append(f"ימים עם צריכה חריגה: {days}")
    lines.append(
        f'חלון השיא של תעו"ז: {rep.taoz_peak_kwh:.0f} קוט"ש '
        f"({rep.taoz_peak_cost_share:.0%} מהעלות אם היית בתעו\"ז)"
    )
    if rep.appliances:
        lines.append("")
        lines.append("זיהוי מכשירים (הערכה הסתברותית מחתימת העומס בלבד, לא ודאות):")
        by_kind: dict[str, list] = {}
        for a in rep.appliances:
            by_kind.setdefault(a.kind, []).append(a)
        for kind, label in _KIND_LABELS.items():
            events = by_kind.get(kind)
            if not events:
                continue
            confs = {}
            for e in events:
                confs[e.confidence] = confs.get(e.confidence, 0) + 1
            conf_txt = ", ".join(f"{n} ב{_CONF_LABELS[c]}" for c, n in sorted(confs.items()))
            lines.append(f"- {label}: {len(events)} אירועים ({conf_txt}).")
            for e in sorted(events, key=lambda x: x.excess_kwh, reverse=True)[:2]:
                lines.append(
                    f"  למשל יום {_HE_DAY[e.start.weekday()]} {e.start:%d.%m %H:%M}-{e.end:%H:%M}"
                    f" ({e.excess_kwh:.1f} קוט\"ש, {_CONF_LABELS[e.confidence]}): {e.pattern}"
                )
    if rep.efficiency:
        lines.append("")
        lines.append("יעילות מכשירים (השוואה לטיפוסי מודרני, בלי פסיקה על מכשיר):")
        for n in rep.efficiency:
            cost = f" הערכת הפרש/עלות שנתית: ~{n.annual_nis:,.0f} ₪." if n.annual_nis is not None else ""
            lines.append(f"- {n.text} ({_CONF_LABELS[n.confidence]}).{cost}")
        lines.append("מקורות ההשוואה: ראו data/benchmarks.json (אומתו ב-2026-11-02)")
    return lines_to_text(lines)

