"""--current-plan: savings vs the household's actual plan (#14)."""
from datetime import datetime, timedelta

from iec_calc import cli
from iec_calc.cost import rank_plans
from iec_calc.parser import Interval
from iec_calc.report import format_ranking
from iec_calc.tariffs import load_catalog


def _intervals():
    start = datetime(2026, 10, 4)
    return [Interval(start + timedelta(minutes=15 * i), 0.1, 0.0) for i in range(96)]


def test_current_plan_marked_and_delta_shown():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    text = format_ranking(costs, 1, cat.flat_rate, current_label="חסכון למשפחות")
    assert "<<< המסלול הנוכחי" in text
    assert "המסלול הנוכחי: סלקום אנרג׳י - חסכון למשפחות" in text
    assert "מול המסלול הנוכחי" in text


def test_no_current_plan_keeps_old_output():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    text = format_ranking(costs, 1, cat.flat_rate)
    assert "המסלול הנוכחי" not in text
    assert "<<< הכי משתלם" in text


def test_unknown_label_errors_with_valid_list(tmp_path, capsys):
    csv = tmp_path / "x.csv"
    csv.write_bytes(
        '\ufeff"00-00000001","צריכה","04/10/2026","00:00",0.1,0\n'.encode("utf-8")
    )
    rc = cli.main(["plans", str(csv), "--current-plan", "אין-כזה-מסלול"])
    assert rc == 2
    assert "no plan matches" in capsys.readouterr().err
