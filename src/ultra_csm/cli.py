"""Ultra CSM command line entrypoint."""

from __future__ import annotations

import argparse
import json
import os

from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.live_smoke import run_smoke


def _connector_smoke(args: argparse.Namespace) -> int:
    result = run_smoke(args.connector_id, env=os.environ, dry_run=args.dry_run)
    payload = {
        "connector_id": result.connector_id,
        "ok": result.ok,
        "state": result.readiness.state,
        "connected": result.readiness.connected,
        "missing_env": result.missing_env,
        "steps": result.steps,
        "errors": result.errors,
        "required_operator_actions": result.readiness.required_operator_actions,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{result.connector_id}: {result.readiness.state}")
        if result.missing_env:
            print("missing env: " + ", ".join(result.missing_env))
        for step in result.steps:
            print(f"ok: {step}")
        for error in result.errors:
            print(f"error: {error}")
    if result.ok:
        return 0
    if result.missing_env:
        return 2
    return 1


def _connector_explore(args: argparse.Namespace) -> int:
    result = run_explorer(args.connector_id, env=os.environ, dry_run=args.dry_run)
    payload = {
        "connector_id": result.connector_id,
        "ok": result.ok,
        "state": result.readiness.state,
        "connected": result.readiness.connected,
        "missing_env": result.missing_env,
        "steps": result.steps,
        "errors": result.errors,
        "required_operator_actions": result.readiness.required_operator_actions,
        "dry_run_requests": result.dry_run_requests,
        "snapshot": result.snapshot.to_dict() if result.snapshot else None,
        "mapping_proposal": (
            result.mapping_proposal.to_dict()
            if result.mapping_proposal
            else None
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{result.connector_id}: {result.readiness.state}")
        if result.missing_env:
            print("missing env: " + ", ".join(result.missing_env))
        for step in result.steps:
            print(f"ok: {step}")
        for request_url in result.dry_run_requests:
            print(f"would request: {request_url}")
        for error in result.errors:
            print(f"error: {error}")
        if result.snapshot is not None:
            print(f"schema_hash: {result.snapshot.schema_hash}")
            print(f"objects: {len(result.snapshot.objects)}")
        if result.mapping_proposal is not None:
            coverage = result.mapping_proposal.coverage
            print(
                "mapping: "
                f"mapped={coverage['mapped']} "
                f"confirm={coverage['ambiguous_confirm']} "
                f"unknown={coverage['missing_to_unknown']}"
            )
            for action in result.mapping_proposal.required_operator_actions:
                print(f"action: {action}")
    if result.ok:
        return 0
    if result.missing_env:
        return 2
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ucsm")
    sub = parser.add_subparsers(dest="command", required=True)

    connectors = sub.add_parser("connectors")
    connector_sub = connectors.add_subparsers(dest="connector_command", required=True)
    smoke = connector_sub.add_parser("smoke")
    smoke.add_argument(
        "connector_id",
        choices=(
            "salesforce_crm",
            "attio_crm",
            "gainsight_cs",
            "rocketlane_onboarding",
            "product_telemetry",
        ),
    )
    smoke.add_argument("--read-only", action="store_true", default=True)
    smoke.add_argument("--dry-run", action="store_true")
    smoke.add_argument("--json", action="store_true")
    smoke.set_defaults(func=_connector_smoke)
    explore = connector_sub.add_parser("explore")
    explore.add_argument(
        "connector_id",
        choices=(
            "salesforce_crm",
            "attio_crm",
            "gainsight_cs",
            "rocketlane_onboarding",
            "product_telemetry",
        ),
    )
    explore.add_argument("--dry-run", action="store_true")
    explore.add_argument("--json", action="store_true")
    explore.set_defaults(func=_connector_explore)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
