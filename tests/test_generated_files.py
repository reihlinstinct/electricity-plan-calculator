"""Generated files must be fresh: regenerate and fail if the committed copy drifts."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_web_data_bundle_is_fresh():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_web_data.py")], check=True)
    diff = subprocess.run(
        ["git", "diff", "--exit-code", "--", "web/tariffs-data.js"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert diff.returncode == 0, (
        "web/tariffs-data.js is stale - run scripts/gen_web_data.py and commit the result\n"
        + diff.stdout
    )
