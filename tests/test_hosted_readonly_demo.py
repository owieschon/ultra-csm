from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_demo_is_static_readonly():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["outputDirectory"] == "ui/out"
    assert "NEXT_PUBLIC_UCSM_READONLY_DEMO=1" in config["buildCommand"]
    assert "functions" not in config
    assert "crons" not in config

    rewrites = {
        (entry["source"], entry["destination"])
        for entry in config["rewrites"]
    }
    assert ("/ui/", "/index.html") in rewrites
    assert ("/ui/comms-review", "/comms-review/index.html") in rewrites
    assert ("/ui/comms-review/", "/comms-review/index.html") in rewrites


def test_hosted_demo_exports_no_write_routes():
    manifest = json.loads(
        (ROOT / "ui" / "public" / "demo-api" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    api_source = (ROOT / "ui" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert manifest["mode"] == "hosted-readonly"
    assert manifest["write_routes_exported"] is False
    assert "The hosted demo is read-only." in api_source
    assert 'method !== "GET" && rawPath !== "/sweep"' in api_source
    assert 'const [rawPath] = path.split("?")' in api_source
    assert 'rawPath === "/demo/action-control/vertical-slice"' in api_source
    assert manifest["action_control_contract_version"] == (
        "action-control.vertical-slice.v1"
    )


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
