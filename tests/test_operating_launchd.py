from __future__ import annotations

from pathlib import Path

from scripts.operating.install_launch_agent import LABEL, render_plist


def test_launch_agent_plist_points_at_current_worktree(tmp_path):
    repo = tmp_path / "repo"
    payload = render_plist(repo_root=repo)

    assert payload["Label"] == LABEL
    assert payload["ProgramArguments"] == [
        "/bin/bash",
        str(repo / "scripts" / "operating" / "daily_run.sh"),
    ]
    assert payload["StartCalendarInterval"] == {"Hour": 7, "Minute": 30}
    assert payload["EnvironmentVariables"]["ULTRA_CSM_OPERATING_ENV_FILE"].endswith(
        "ultra-csm-operating.env"
    )


def test_daily_run_script_no_longer_hard_codes_old_worktree():
    script = Path("scripts/operating/daily_run.sh").read_text(encoding="utf-8")

    assert "ultra-csm-operating-cadence" not in script
    assert "SCRIPT_DIR=" in script
    assert "ULTRA_CSM_OPERATING_ENV_FILE" in script
