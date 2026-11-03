"""--current-plan: savings vs the household's actual plan (#14)."""

from datetime import datetime, timedelta

from iec_calc import cli
from iec_calc.cost import Customer, rank_plans
from iec_calc.parser import Interval
from iec_calc.report import format_ranking
from iec_calc.tariffs import load_catalog


def _intervals():
    start = datetime(2026, 10, 4)
    return [Interval(start + timedelta(minutes=15 * i), 0.1, 0.0) for i in range(96)]


def test_current_plan_marked_and_delta_shown():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    text = format_ranking(costs, 1, cat, current_label="חסכון למשפחות")
    assert "<<< המסלול הנוכחי" in text
    assert "המסלול הנוכחי: סלקום אנרג׳י - חסכון למשפחות" in text
    assert "מול המסלול הנוכחי" in text


def test_no_current_plan_keeps_old_output():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    text = format_ranking(costs, 1, cat)
    assert "המסלול הנוכחי" not in text
    assert "<<< הכי משתלם" in text


def test_unknown_label_errors_with_valid_list(tmp_path, capsys):
    csv = tmp_path / "x.csv"
    csv.write_bytes('\ufeff"00-00000001","צריכה","04/10/2026","00:00",0.1,0\n'.encode("utf-8"))
    rc = cli.main(["plans", str(csv), "--current-plan", "אין-כזה-מסלול"])
    assert rc == 2
    assert "no plan matches" in capsys.readouterr().err


def test_ambiguous_label_errors(tmp_path, capsys):
    csv = tmp_path / "x.csv"
    csv.write_bytes('\ufeff"00-00000001","צריכה","04/10/2026","00:00",0.1,0\n'.encode("utf-8"))
    rc = cli.main(["plans", str(csv), "--current-plan", "סלקום"])
    assert rc == 2
    assert "ambiguous" in capsys.readouterr().err


def test_label_validated_before_csv_parse(capsys):
    rc = cli.main(["plans", "/nonexistent/file.csv", "--current-plan", "אין-כזה-מסלול"])
    assert rc == 2
    assert "no plan matches" in capsys.readouterr().err


def test_taoz_fee_text_from_catalog():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    text = format_ranking(costs, 1, cat)
    assert f"{cat.taoz.fixed_fee_monthly_pre_vat:.2f}" in text


def test_flat_and_taoz_labels_accepted(tmp_path, capsys):
    csv = tmp_path / "x.csv"
    csv.write_bytes('\ufeff"00-00000001","צריכה","04/10/2026","00:00",0.1,0\n'.encode("utf-8"))
    for label in ("תעריף אחיד", 'תעו"ז'):
        rc = cli.main(["plans", str(csv), "--current-plan", label])
        assert rc == 0, label


def test_current_plan_top_ranked_message():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1)
    top_label = costs[0].label
    text = format_ranking(costs, 1, cat, current_label=top_label)
    assert "הכי משתלם (המסלול הנוכחי שלך)" in text
    assert "המסלול הנוכחי שלך הוא הזול ביותר" in text
    assert "חוסך" not in text.split("המסלול הנוכחי:")[1].split("\n")[1]


def test_current_plan_excluded_notice():
    cat = load_catalog()
    costs = rank_plans(_intervals(), cat, days=1, customer=Customer(gas_customer=False))
    text = format_ranking(costs, 1, cat, current_label="אמישראגז")
    assert "לא נכלל בדירוג עקב דגלי הזכאות" in text
