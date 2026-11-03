from pathlib import Path

from iec_calc import resources


def test_checkout_resource_paths():
    root = Path(__file__).resolve().parents[1]
    assert resources.resource_path("strings.json") == root / "i18n" / "strings.json"
    assert resources.resource_path("tariffs.json") == root / "data" / "tariffs.json"
    assert resources.resource_path("benchmarks.json") == root / "data" / "benchmarks.json"


def test_bundled_resources_preferred(tmp_path, monkeypatch):
    package = tmp_path / "iec_calc"
    bundled = package / "resources" / "strings.json"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("{}")
    monkeypatch.setattr(resources, "__file__", str(package / "resources.py"))
    assert resources.resource_path("strings.json") == bundled
