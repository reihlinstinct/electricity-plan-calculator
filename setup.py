"""Copy canonical runtime JSON into distributions, without maintained duplicates."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
RESOURCES = {
    "strings.json": ROOT / "i18n" / "strings.json",
    "tariffs.json": ROOT / "data" / "tariffs.json",
    "benchmarks.json": ROOT / "data" / "benchmarks.json",
}


class BuildWithResources(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "iec_calc" / "resources"
        target.mkdir(parents=True, exist_ok=True)
        for name, source in RESOURCES.items():
            self.copy_file(str(source), str(target / name))


setup(cmdclass={"build_py": BuildWithResources})
