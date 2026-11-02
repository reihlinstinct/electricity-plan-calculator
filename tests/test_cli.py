import logging

from iec_calc.cli import main


def test_report_runs(sample_csv, capsys):
    rc = main(["report", str(sample_csv)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ניתוח צריכה" in out
    assert "דירוג מסלולים" in out
    assert "<<< הכי משתלם" in out
    assert "ELECTRA POWER - Power" in out  # 6.5% flat wins on this profile... or any flat plan


def test_plans_only(sample_csv, capsys):
    rc = main(["plans", str(sample_csv)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "דירוג מסלולים" in out
    assert "ניתוח צריכה" not in out


def test_analyze_only(sample_csv, capsys):
    rc = main(["analyze", str(sample_csv)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "עומס בסיס" in out
    assert "דירוג מסלולים" not in out


def test_bad_file_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("x,y,z\n", encoding="utf-8")
    rc = main(["analyze", str(bad)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_debug_flag_enables_debug_logging(sample_csv):
    main(["--debug", "plans", str(sample_csv)])
    assert logging.getLogger().level == logging.DEBUG
    main(["plans", str(sample_csv)])
    assert logging.getLogger().level == logging.WARNING


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    assert "iec-calc" in capsys.readouterr().out


def test_cli_gas_hot_opt_in(sample_csv, capsys):
    from iec_calc.cli import main
    def ranked_lines(out):
        return [ln for ln in out.splitlines() if " | " in ln]

    main(["plans", str(sample_csv)])
    out = capsys.readouterr().out
    assert not any("אמישראגז" in ln for ln in ranked_lines(out))
    main(["plans", str(sample_csv), "--gas"])
    out = capsys.readouterr().out
    assert any("אמישראגז" in ln for ln in ranked_lines(out))
