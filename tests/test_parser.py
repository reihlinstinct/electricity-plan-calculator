import csv
from datetime import datetime

import pytest

from iec_calc.parser import parse


def test_parse_sample(sample_csv):
    intervals = parse(sample_csv)
    assert len(intervals) == 14 * 96
    assert intervals == sorted(intervals, key=lambda i: i.start)
    assert all(i.kwh >= 0 for i in intervals)


def test_parse_skips_metadata_and_malformed(tmp_path):
    p = tmp_path / "export.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["שם לקוח", "כתובת", "מספר חוזה"])
        w.writerow(["ישראלה ישראלי", "רחוב הדוגמה 3 חיפה", "000000000000"])
        w.writerow(["00-00000001", "צריכה", "01/10/2026", "00:00", "0.5", "0"])
        w.writerow(["00-00000001", "צריכה", "not-a-date", "00:15", "0.5", "0"])
        w.writerow(["00-00000001", "צריכה", "01/10/2026", "00:15", "0.25", ""])
        w.writerow(["00-00000001", "הזרמה", "01/10/2026", "00:30", "0.9", "0.9"])
    intervals = parse(p)
    assert len(intervals) == 2
    assert intervals[0].start == datetime(2026, 10, 1, 0, 0)
    assert intervals[1].kwh == 0.25


def test_parse_no_data_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("nothing,here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no consumption intervals"):
        parse(p)


def test_bom_handled(tmp_path):
    p = tmp_path / "bom.csv"
    p.write_bytes('\ufeff"00-00000001","צריכה","02/10/2026","10:00",0.7,0\n'.encode("utf-8"))
    intervals = parse(p)
    assert len(intervals) == 1
    assert intervals[0].kwh == 0.7


def test_2400_normalized(tmp_path):
    p = tmp_path / "h24.csv"
    p.write_bytes('\ufeff"00-00000001","צריכה","02/10/2026","24:00",0.7,0\n'.encode("utf-8"))
    intervals = parse(p)
    assert intervals[0].start == datetime(2026, 10, 3, 0, 0)


@pytest.mark.parametrize("bad_time", ["24:30", "25:00", "99:00", "-1:00", "12:60", "12:-1"])
def test_invalid_interval_times_skipped(tmp_path, bad_time):
    p = tmp_path / "invalid-time.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for stamp in (bad_time, "23:45", "24:00"):
            writer.writerow(["00-00000001", "צריכה", "02/10/2026", stamp, "0.7", "0"])
    intervals = parse(p)
    assert [i.start for i in intervals] == [
        datetime(2026, 10, 2, 23, 45),
        datetime(2026, 10, 3, 0, 0),
    ]


def test_only_invalid_interval_time_raises(tmp_path):
    p = tmp_path / "invalid-only.csv"
    p.write_text('"00-00000001","צריכה","02/10/2026","24:30",0.7,0\n', encoding="utf-8")
    with pytest.raises(ValueError, match="no consumption intervals"):
        parse(p)
