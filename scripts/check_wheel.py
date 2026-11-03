"""Smoke-test a built wheel in isolation from checkout and editable installs."""

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(wheel: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        with zipfile.ZipFile(wheel) as archive:
            for name, source in (
                ("strings.json", ROOT / "i18n" / "strings.json"),
                ("tariffs.json", ROOT / "data" / "tariffs.json"),
                ("benchmarks.json", ROOT / "data" / "benchmarks.json"),
            ):
                assert json.loads(archive.read("iec_calc/resources/" + name)) == json.loads(source.read_text())
            archive.extractall(target)
        code = """
import sys
sys.path.insert(0, sys.argv[1])
from iec_calc import i18n, tariffs, benchmarks, mcp_server
from pathlib import Path
assert Path(i18n.__file__).is_relative_to(Path(sys.argv[1]))
from iec_calc.cli import main
assert {"he", "en", "ar", "ru", "am"} <= i18n.languages().keys()
assert tariffs.load_catalog().plans
assert benchmarks.load_benchmarks().washer_typical_kwh_per_cycle > 0
assert main(['--lang', 'en', 'report', sys.argv[2]]) == 0
print('installed wheel smoke passed')
"""
        # -I ignores PYTHONPATH and user site packages, so an editable source
        # tree cannot accidentally rescue a broken wheel.
        subprocess.run(
            [sys.executable, "-I", "-c", code, str(target), str(ROOT / "data" / "sample_consumption.csv")],
            cwd=target,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            check=True,
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
