"""Ultra CSM command line entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request

from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.live_smoke import run_smoke
from ultra_csm.data_plane.synthetic_book import build_synthetic_book, synthetic_book_summary

DEFAULT_API_URL = "http://127.0.0.1:8000"


class CliApiError(RuntimeError):
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("error") or payload.get("detail") or payload))
        self.status = status
        self.payload = payload


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


def _demo_book(args: argparse.Namespace) -> int:
    data = build_synthetic_book()
    if args.json:
        payload = {
            "accounts": len(data.accounts),
            "companies": len(data.companies),
            "contacts": len(data.contacts),
            "cases": len(data.cases),
            "opportunities": len(data.opportunities),
            "health_scores": len(data.health_scores),
            "ctas": len(data.ctas),
            "success_plans": len(data.success_plans),
            "adoption_summaries": len(data.adoption_summaries),
            "entitlements": len(data.entitlements),
            "usage_signals": len(data.usage_signals),
            "milestones": len(data.milestones),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(synthetic_book_summary(data))
    return 0


def _proposal_list(args: argparse.Namespace) -> int:
    try:
        payload = _api_json(args.api_url, "/proposals")
    except CliApiError as exc:
        return _print_api_error(exc, json_output=args.json)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    proposals = payload.get("proposals", [])
    print(f"pending proposals: {payload.get('pending_count', len(proposals))}")
    for proposal in proposals:
        body = proposal.get("payload", {})
        account = body.get("account_name") or body.get("account_id") or "unknown-account"
        print(
            f"{proposal['proposal_id']}  "
            f"{proposal['action']}  "
            f"tier={proposal['autonomy_tier']}  "
            f"{proposal['status']}  "
            f"{account}"
        )
    return 0


def _proposal_show(args: argparse.Namespace) -> int:
    try:
        payload = _api_json(args.api_url, "/proposals")
    except CliApiError as exc:
        return _print_api_error(exc, json_output=args.json)
    proposal = next(
        (
            item for item in payload.get("proposals", [])
            if item.get("proposal_id") == args.proposal_id
        ),
        None,
    )
    if proposal is None:
        error_payload = {
            "error": "Proposal not found in pending queue",
            "proposal_id": args.proposal_id,
        }
        if args.json:
            print(json.dumps(error_payload, indent=2, sort_keys=True))
        else:
            print(f"error: {error_payload['error']} ({args.proposal_id})")
        return 1
    if args.json:
        print(json.dumps(proposal, indent=2, sort_keys=True))
    else:
        print(f"proposal: {proposal['proposal_id']}")
        print(f"action: {proposal['action']}")
        print(f"tier: {proposal['autonomy_tier']}")
        print(f"status: {proposal['status']}")
        print(f"required_permission: {proposal['required_permission']}")
        print("payload:")
        print(json.dumps(proposal.get("payload", {}), indent=2, sort_keys=True))
    return 0


def _proposal_verdict(args: argparse.Namespace) -> int:
    reason = args.reason or f"{args.verdict.title()} via ucsm CLI"
    try:
        payload = _api_json(
            args.api_url,
            f"/proposals/{args.proposal_id}/verdict",
            method="POST",
            payload={"verdict": args.verdict, "reason": reason},
        )
    except CliApiError as exc:
        return _print_api_error(exc, json_output=args.json)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['proposal_id']}: "
            f"{payload['status']} "
            f"(authorized={str(payload['authorized']).lower()})"
        )
    return 0


def _api_json(
    api_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        api_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        raise CliApiError(exc.code, _decode_error_payload(text)) from exc
    except error.URLError as exc:
        raise CliApiError(2, {"error": f"API unavailable: {exc.reason}"}) from exc


def _decode_error_payload(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return {"error": text}
    if isinstance(raw, dict):
        detail = raw.get("detail")
        if isinstance(detail, dict):
            return detail
        return raw
    return {"error": str(raw)}


def _print_api_error(exc: CliApiError, *, json_output: bool) -> int:
    if json_output:
        print(json.dumps(exc.payload, indent=2, sort_keys=True))
    else:
        print(f"error: {exc}")
    return 2 if exc.status == 2 else 1


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

    demo_book = sub.add_parser("demo-book", help="Print synthetic book of business summary")
    demo_book.add_argument("--json", action="store_true")
    demo_book.set_defaults(func=_demo_book)

    proposals = sub.add_parser("proposals")
    proposal_sub = proposals.add_subparsers(dest="proposal_command", required=True)

    list_cmd = proposal_sub.add_parser("list")
    _add_api_args(list_cmd)
    list_cmd.set_defaults(func=_proposal_list)

    show_cmd = proposal_sub.add_parser("show")
    show_cmd.add_argument("proposal_id")
    _add_api_args(show_cmd)
    show_cmd.set_defaults(func=_proposal_show)

    approve_cmd = proposal_sub.add_parser("approve")
    approve_cmd.add_argument("proposal_id")
    approve_cmd.add_argument("--reason", default=None)
    _add_api_args(approve_cmd)
    approve_cmd.set_defaults(func=_proposal_verdict, verdict="approve")

    reject_cmd = proposal_sub.add_parser("reject")
    reject_cmd.add_argument("proposal_id")
    reject_cmd.add_argument("--reason", default=None)
    _add_api_args(reject_cmd)
    reject_cmd.set_defaults(func=_proposal_verdict, verdict="deny")
    return parser


def _add_api_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-url",
        default=os.environ.get("ULTRA_CSM_API_URL", DEFAULT_API_URL),
        help="Ultra CSM API base URL",
    )
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
