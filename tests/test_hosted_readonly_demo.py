from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_demo_is_static_readonly():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["outputDirectory"] == "ui/out"
    assert "NEXT_PUBLIC_UCSM_READONLY_DEMO=1" in config["buildCommand"]
    assert "functions" not in config
    assert "crons" not in config

    rewrites = {(entry["source"], entry["destination"]) for entry in config["rewrites"]}
    assert ("/ui/", "/index.html") in rewrites
    assert ("/ui/comms-review", "/comms-review/index.html") in rewrites
    assert ("/ui/comms-review/", "/comms-review/index.html") in rewrites
    assert ("/ui/action-control", "/action-control/index.html") in rewrites
    assert ("/ui/action-control/", "/action-control/index.html") in rewrites


def test_hosted_demo_make_target_declares_safe_local_noauth_boundary():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("hosted-readonly-demo:\n", 1)[1].split("\n\n", 1)[0]

    assert "ULTRA_CSM_BIND_HOST=127.0.0.1" in target
    assert "ULTRA_CSM_DEMO_NOAUTH=1" in target
    assert "scripts/export_hosted_readonly_demo.py" in target
    assert "--check" in target


def test_ci_checks_committed_scorecard_without_regenerating_first():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "run: make scorecard-csm-check" in workflow
    assert "run: make scorecard-csm\n" not in workflow
    assert "run: make hosted-readonly-demo-check" in workflow
    assert "needs: eval" in workflow


def test_hosted_demo_exports_no_write_routes():
    manifest = json.loads(
        (ROOT / "ui" / "public" / "demo-api" / "manifest.json").read_text(encoding="utf-8")
    )
    api_source = (ROOT / "ui" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert manifest["mode"] == "hosted-readonly"
    assert manifest["write_routes_exported"] is False
    assert "The hosted demo is read-only." in api_source
    assert 'method !== "GET" && rawPath !== "/sweep"' in api_source
    assert 'const [rawPath] = path.split("?")' in api_source
    assert 'rawPath === "/demo/action-control/vertical-slice"' in api_source
    assert manifest["action_control_contract_version"] == ("action-control.vertical-slice.v1")
    sandbox_api = (ROOT / "ui" / "lib" / "actionControlApi.ts").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API" in sandbox_api
    assert "Interactive sandbox backend is not deployed" in sandbox_api


def test_hosted_demo_has_core_fixtures():
    fixture_dir = ROOT / "ui" / "public" / "demo-api"
    expected = {
        "health.json",
        "accounts-day-140.json",
        "sweep-day-140.json",
        "proposals.json",
        "ledger.json",
        "action-control-vertical-slice-v1.json",
        "comms-slack.json",
        "comms-notion.json",
    }
    assert expected <= {path.name for path in fixture_dir.glob("*.json")}


def test_hosted_demo_has_work_packets_for_every_queue_item():
    sweep = json.loads(
        (ROOT / "ui" / "public" / "demo-api" / "sweep-day-140.json").read_text(encoding="utf-8")
    )

    assert len(sweep["work_items"]) == 12
    assert sum(item.get("work_packet") is not None for item in sweep["work_items"]) == 12


def test_two_independent_hosted_exports_have_identical_hashes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    _run_export(first)
    _run_export(second)

    assert _fixture_hashes(first) == _fixture_hashes(second)


def test_hosted_export_is_independent_of_caller_timezone(tmp_path):
    new_york = tmp_path / "new-york"
    utc = tmp_path / "utc"

    _run_export(new_york, timezone="America/New_York")
    _run_export(utc, timezone="UTC")

    assert _fixture_hashes(new_york) == _fixture_hashes(utc)


def _run_export(output_dir: Path, *, timezone: str | None = None) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    env["ULTRA_CSM_BIND_HOST"] = "127.0.0.1"
    env["ULTRA_CSM_DEMO_NOAUTH"] = "1"
    if timezone is not None:
        env["TZ"] = timezone
    subprocess.run(
        [
            sys.executable,
            "scripts/export_hosted_readonly_demo.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _fixture_hashes(output_dir: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output_dir.glob("*.json"))
    }
