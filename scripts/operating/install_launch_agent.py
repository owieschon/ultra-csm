#!/usr/bin/env python3
"""Install the Ultra CSM daily LaunchAgent for the current worktree."""

from __future__ import annotations

import argparse
import plistlib
import subprocess
from pathlib import Path

LABEL = "com.ultracsm.operating-daily"
DEFAULT_ENV_FILE = Path.home() / "ultra-csm-operating.env"
DEFAULT_RUNS_ROOT = Path.home() / "ultra-csm-operating-runs"


def render_plist(
    *,
    repo_root: Path,
    env_file: Path = DEFAULT_ENV_FILE,
    runs_root: Path = DEFAULT_RUNS_ROOT,
    hour: int = 7,
    minute: int = 30,
) -> dict[str, object]:
    script = repo_root / "scripts" / "operating" / "daily_run.sh"
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "RunAtLoad": False,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(runs_root / "operating_stdout.log"),
        "StandardErrorPath": str(runs_root / "operating_stderr.log"),
        "EnvironmentVariables": {
            "LC_ALL": "en_US.UTF-8",
            "LANG": "en_US.UTF-8",
            "ULTRA_CSM_OPERATING_ENV_FILE": str(env_file),
        },
        "WorkingDirectory": str(repo_root),
    }


def write_plist(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)


def launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        check=True,
        text=True,
        capture_output=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--plist",
        type=Path,
        default=Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist",
    )
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--unload", action="store_true")
    args = parser.parse_args(argv)

    payload = render_plist(repo_root=args.repo_root.resolve(), env_file=args.env_file)
    write_plist(payload, args.plist)

    if args.unload:
        launchctl("unload", str(args.plist))
    if args.load:
        launchctl("load", str(args.plist))
    print(args.plist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
