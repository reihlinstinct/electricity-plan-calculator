#!/usr/bin/env python3
"""Generate a synthetic IEC-shaped consumption export for tests and demos.

Fully fictional: name, address, contract and meter numbers are placeholders.
"""

import csv
import random
from datetime import date, datetime, time, timedelta

random.seed(20261102)
START = date(2026, 10, 1)
DAYS = 14


def interval_kwh(dt: datetime) -> float:
    h = dt.hour + dt.minute / 60
    base = 0.04 + random.random() * 0.02
    if 7 <= h < 17:
        base += 0.05 + random.random() * 0.05
    if 17 <= h < 23:
        base += 0.15 + random.random() * 0.12
    if dt.weekday() in (4, 5):  # Fri-Sat: at-home weekend bump
        base *= 1.5
    return round(base, 3)


def main() -> None:
    with open("data/sample_consumption.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow([" ", "  ", "  "])
        w.writerow(["שם לקוח", "כתובת", "מספר חוזה"])
        w.writerow(["ישראלה ישראלי", "רחוב הדוגמה 3 דירה 2 חיפה", "000000000000"])
        w.writerow(["סוג מונה", "קוד מונה", "מספר מונה"])
        w.writerow(["צריכה", "00", "00000001"])
        w.writerow(["קוד ומספר מונה", "סוג מונה", "תאריך", "מועד תחילת הפעימה", 'צריכה/ייצור בקוט"ש', 'הזרמה בקוט"ש'])
        d = START
        for _ in range(DAYS):
            for slot in range(96):
                hh, mm = divmod(slot * 15, 60)
                dt = datetime.combine(d, time(hh, mm))
                w.writerow(["00-00000001", "צריכה", d.strftime("%d/%m/%Y"), f"{hh:02d}:{mm:02d}", interval_kwh(dt), 0])
            d += timedelta(days=1)


if __name__ == "__main__":
    main()
