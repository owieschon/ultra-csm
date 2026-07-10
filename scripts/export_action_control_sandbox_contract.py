"""Generate or verify the public Action Control sandbox response schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ultra_csm.action_control_sandbox_contract import action_control_sandbox_json_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "contracts" / "action-control.sandbox-session.v1.schema.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(action_control_sandbox_json_schema(), indent=2, sort_keys=True) + "\n"
    if args.check:
        actual = SCHEMA_PATH.read_text(encoding="utf-8") if SCHEMA_PATH.exists() else ""
        if actual != expected:
            print(f"stale: {SCHEMA_PATH.relative_to(ROOT)}")
            return 1
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(expected, encoding="utf-8")
    print(f"wrote {SCHEMA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
