"""Locate canonical source resources or their bundled installed copies."""

from pathlib import Path


def resource_path(filename: str) -> Path:
    package = Path(__file__).resolve().parent
    bundled = package / "resources" / filename
    if bundled.is_file():
        return bundled
    folder = "i18n" if filename == "strings.json" else "data"
    return package.parents[1] / folder / filename
