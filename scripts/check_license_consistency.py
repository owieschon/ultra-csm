#!/usr/bin/env python3
"""Fail when Ultra CSM's public license surfaces disagree."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPECTED = "Apache-2.0"
README_LICENSE_LINE = "Apache-2.0 — see [LICENSE](LICENSE)."


def main() -> int:
    python_license = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["license"]
    ui_license = json.loads((ROOT / "ui/package.json").read_text())["license"]
    license_text = (ROOT / "LICENSE").read_text()
    readme = (ROOT / "README.md").read_text()
    checks = {
        "pyproject.toml": python_license == EXPECTED,
        "ui/package.json": ui_license == EXPECTED,
        "LICENSE": "Apache License" in license_text and "Version 2.0" in license_text,
        "README.md": README_LICENSE_LINE in readme,
    }
    failed = [path for path, ok in checks.items() if not ok]
    print(json.dumps({"license": EXPECTED if not failed else None, "surfaces": checks}, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
