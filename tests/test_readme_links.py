"""Keep the hosted calculator discoverable without showing a bare URL."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_readme_links_to_calculator_with_descriptive_text():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    url = "https://reihlinstinct.github.io/electricity-plan-calculator/web/"
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", readme)
    labels = [label for label, destination in links if destination == url]
    assert labels, "README must link to the live calculator, not the Pages root"
    assert all("calculator" in label.lower() and "http" not in label.lower() for label in labels)
    without_markdown_links = re.sub(r"\[[^\]]+\]\([^)]+\)", "", readme)
    assert url not in without_markdown_links, "calculator URL must not be shown bare"


def test_pages_root_readme_fallback_targets_repository_document():
    root_page = (ROOT / "index.md").read_text(encoding="utf-8")
    target = "https://github.com/reihlinstinct/electricity-plan-calculator/blob/main/README.md"
    assert f"[Project README]({target})" in root_page
    assert 'content="0; url=web/"' in root_page
    assert "[Open the electricity plan calculator](web/)" in root_page
