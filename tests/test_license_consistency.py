from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_public_license_surfaces_are_consistent() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_license_consistency.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"license": "Apache-2.0"' in result.stdout
