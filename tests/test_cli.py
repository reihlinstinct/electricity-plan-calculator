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
    assert "רצפת צריכה" in out
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


def test_report_runs_arabic(sample_csv, capsys):
    import iec_calc.i18n as i18n
    try:
        rc = main(["--lang", "ar", "report", str(sample_csv)])
    finally:
        i18n.set_active_language(None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "تحليل الاستهلاك" in out
    assert "ترتيب المسارات" in out
    # supplier plan names stay Hebrew (proper nouns from the tariff catalog)
    assert "ELECTRA POWER" in out


def test_report_runs_russian(sample_csv, capsys):
    import iec_calc.i18n as i18n
    try:
        rc = main(["--lang", "ru", "report", str(sample_csv)])
    finally:
        i18n.set_active_language(None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Анализ потребления" in out
    assert "Рейтинг планов" in out
    # supplier plan names stay Hebrew (proper nouns from the tariff catalog)
    assert "ELECTRA POWER" in out


def test_report_runs_amharic(sample_csv, capsys):
    import iec_calc.i18n as i18n
    try:
        rc = main(["--lang", "am", "report", str(sample_csv)])
    finally:
        i18n.set_active_language(None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "የፍጆታ ትንታኔ" in out
    assert "የዕቅዶች ደረጃ ሰሌዳ" in out
    # supplier plan names stay Hebrew (proper nouns from the tariff catalog)
    assert "ELECTRA POWER" in out


def test_cli_phase_controls_fixed_fees(sample_csv, capsys, monkeypatch):
    import iec_calc.cli as cli
    original = cli.cost.rank_plans
    seen = []

    def record_phase(*args, **kwargs):
        ranked = original(*args, **kwargs)
        seen.append((kwargs["phase"], {p.kind: p.annual_cost for p in ranked}))
        return ranked

    monkeypatch.setattr(cli.cost, "rank_plans", record_phase)
    assert main(["plans", str(sample_csv)]) == 0
    capsys.readouterr()
    assert main(["plans", str(sample_csv), "--phase", "three"]) == 0
    capsys.readouterr()
    assert [phase for phase, _ in seen] == ["single", "three"]
    single, three = seen[0][1], seen[1][1]
    assert abs(three["flat"] - single["flat"] - (27.09 - 25.57) * 12 * 1.18) < 0.01
    assert three["taoz"] == single["taoz"]
