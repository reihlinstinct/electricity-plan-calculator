"""Smoke-test a built wheel in isolation from checkout and editable installs."""

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(wheel: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        with zipfile.ZipFile(wheel) as archive:
            metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = Parser().parsestr(archive.read(metadata_name).decode())
            assert metadata["Requires-Python"] == ">=3.11"
            for name, source in (
                ("strings.json", ROOT / "i18n" / "strings.json"),
                ("tariffs.json", ROOT / "data" / "tariffs.json"),
                ("benchmarks.json", ROOT / "data" / "benchmarks.json"),
            ):
                assert json.loads(archive.read("iec_calc/resources/" + name)) == json.loads(source.read_text())
            # the wheel's languages are exactly the source catalog's (no fixed list here)
            catalog_langs = list(json.loads((ROOT / "i18n" / "strings.json").read_text())["languages"])
            archive.extractall(target)
        code = """
import sys, io, contextlib, json
assert sys.version_info >= (3, 11), "Python 3.11+ required"
sys.path.insert(0, sys.argv[1])
from iec_calc import i18n, tariffs, benchmarks, mcp_server
from pathlib import Path
assert Path(i18n.__file__).is_relative_to(Path(sys.argv[1]))
from iec_calc.cli import main
langs = i18n.languages()
assert list(langs) == json.loads(sys.argv[3]), 'wheel languages differ from the source catalog'
assert all(i18n.t('ui.title', lang=code) for code in langs)
other = next(code for code, meta in langs.items() if not meta.get('default'))
assert tariffs.load_catalog().plans
assert benchmarks.load_benchmarks().washer_typical_kwh_per_cycle > 0
with contextlib.redirect_stdout(io.StringIO()) as output:
    assert main(['--lang', other, 'report', sys.argv[2]]) == 0
assert str(Path(sys.argv[1]) / 'iec_calc' / 'resources' / 'benchmarks.json') in output.getvalue()
print('installed wheel smoke passed')
"""
        # -I ignores PYTHONPATH and user site packages, so an editable source
        # tree cannot accidentally rescue a broken wheel.
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                code,
                str(target),
                str(ROOT / "data" / "sample_consumption.csv"),
                json.dumps(catalog_langs),
            ],
            cwd=target,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            check=True,
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
