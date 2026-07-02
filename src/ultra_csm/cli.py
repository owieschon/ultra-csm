"""Ultra CSM command line entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
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


def _score_book(
    data: "FixtureCustomerData",
    as_of: str,
) -> list[dict[str, Any]]:
    """Score all accounts in a FixtureCustomerData, return list of dicts."""
    from ultra_csm.data_plane.contracts import CustomerDataPlane
    from ultra_csm.data_plane.fixtures import (
        FixtureCRMDataConnector,
        FixtureCSPlatformConnector,
        FixtureProductTelemetryConnector,
    )
    from ultra_csm.value_model import (
        build_customer_value_model,
        load_value_model_config,
        project_ttv_lens,
    )

    crm = FixtureCRMDataConnector(data=data)
    cs = FixtureCSPlatformConnector(data=data)
    telemetry = FixtureProductTelemetryConnector(data=data)
    config = load_value_model_config()
    results: list[dict[str, Any]] = []

    for account in data.accounts:
        aid = account.account_id
        company = cs.get_company(aid)
        health = cs.get_health_score(aid)
        adoption = cs.get_adoption_summary(aid)
        entitlements = tuple(telemetry.list_entitlements(aid))
        usage_signals = tuple(telemetry.list_usage_signals(aid))
        success_plans = tuple(cs.list_success_plans(aid))
        milestones = tuple(telemetry.list_ttv_milestones(aid))

        if company is None or health is None:
            continue

        model = build_customer_value_model(
            account=account,
            company=company,
            health=health,
            adoption=adoption,
            entitlements=entitlements,
            usage_signals=usage_signals,
            success_plans=success_plans,
            config=config,
        )

        open_milestones = tuple(
            m for m in milestones
            if m.achieved_at is None
            and m.expected_by < as_of
        )
        overdue_plans = tuple(
            p for p in success_plans
            if p.status in ("active",)
            and p.target_date < as_of
        )

        priority = project_ttv_lens(
            model,
            company=company,
            health=health,
            open_milestone_gaps=open_milestones,
            overdue_success_plans=overdue_plans,
            as_of=as_of,
        )

        results.append({
            "account_id": aid,
            "name": account.name,
            "health_band": health.band,
            "health_score": health.score,
            "health_drivers": list(health.drivers),
            "priority_score": priority.score,
            "priority_factors": [f.name for f in priority.factors],
            "arr_cents": company.arr_cents,
            "lifecycle_stage": company.lifecycle_stage,
            "renewal_date": company.renewal_date,
        })

    results.sort(key=lambda r: r["priority_score"], reverse=True)
    return results


def _apply_deep_data_overlay(
    data: "FixtureCustomerData",
    day: int,
) -> "FixtureCustomerData":
    """Overlay deep simulation aggregates onto a FixtureCustomerData snapshot.

    Recomputes AdoptionSummary active_users and active_assets from the deep
    data simulation's per-user login histories and feature adoption states.
    """
    from ultra_csm.data_plane.contracts import AdoptionSummary, UsageSignal
    from ultra_csm.data_plane.data_simulator import simulate_data

    bundle = simulate_data(data, day=day)

    adoption_by_id: dict[str, AdoptionSummary] = {
        a.account_id: a for a in data.adoption_summaries
    }
    signal_by_key: dict[tuple[str, str], UsageSignal] = {
        (s.account_id, s.metric_name): s for s in data.usage_signals
    }

    new_adoptions: list[AdoptionSummary] = []
    for adoption in data.adoption_summaries:
        ab = bundle.accounts.get(adoption.account_id)
        if ab is None:
            new_adoptions.append(adoption)
            continue

        # Recompute active users and adoption rate from deep data
        active_users = ab.active_user_count
        entitled_assets = adoption.entitled_assets
        # Estimate active assets proportionally from feature depth
        if ab.feature_depth_score > 0 and entitled_assets > 0:
            active_assets = max(
                active_users,
                int(entitled_assets * ab.feature_depth_score * 0.9),
            )
        else:
            active_assets = 0
        rate = round(active_assets / entitled_assets, 2) if entitled_assets > 0 else 0.0

        # Identify underused capabilities from feature adoption
        underused = tuple(
            f.feature for f in ab.feature_adoptions
            if f.status in ("not_started", "exploring")
        )

        from ultra_csm.data_plane.book_simulator import _day_clock
        new_adoptions.append(AdoptionSummary(
            account_id=adoption.account_id,
            active_users=min(active_users, adoption.licensed_users),
            licensed_users=adoption.licensed_users,
            active_assets=active_assets,
            entitled_assets=entitled_assets,
            adoption_rate=rate,
            underused_capabilities=underused,
            measured_at=_day_clock(day),
        ))

        # Also update the daily_active_assets usage signal
        sig_key = (adoption.account_id, "daily_active_assets")
        if sig_key in signal_by_key:
            old = signal_by_key[sig_key]
            signal_by_key[sig_key] = UsageSignal(
                signal_id=old.signal_id,
                account_id=old.account_id,
                grain=old.grain,
                subject_id=old.subject_id,
                metric_name=old.metric_name,
                value=float(active_assets),
                unit=old.unit,
                observed_at=_day_clock(day),
                source_ref=old.source_ref,
            )

    # Rebuild usage signals
    seen: set[tuple[str, str]] = set()
    new_signals: list[UsageSignal] = []
    for sig in data.usage_signals:
        key = (sig.account_id, sig.metric_name)
        repl = signal_by_key.get(key)
        if repl is not None and key not in seen:
            new_signals.append(repl)
            seen.add(key)
        else:
            new_signals.append(sig)

    from ultra_csm.data_plane.fixtures import FixtureCustomerData as FCD
    return FCD(
        accounts=data.accounts,
        companies=data.companies,
        contacts=data.contacts,
        cases=data.cases,
        opportunities=data.opportunities,
        health_scores=data.health_scores,
        ctas=data.ctas,
        success_plans=data.success_plans,
        adoption_summaries=tuple(new_adoptions),
        entitlements=data.entitlements,
        usage_signals=tuple(new_signals),
        milestones=data.milestones,
        tenant_accounts=data.tenant_accounts,
    )


def _demo_sweep(args: argparse.Namespace) -> int:
    from ultra_csm.data_plane.book_simulator import simulate_book
    from ultra_csm.data_plane.synthetic_book import SEED_DATE

    day = args.day
    base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
    as_of = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")

    base_book = build_synthetic_book()
    if day == 0:
        mutated = base_book
    else:
        mutated = simulate_book(base_book, day_offset=day)

    # Overlay deep data simulation when --deep is set
    if getattr(args, "deep", False) and day > 0:
        mutated = _apply_deep_data_overlay(mutated, day)

    scored = _score_book(mutated, as_of)

    # Health distribution
    green = sum(1 for r in scored if r["health_band"] == "green")
    yellow = sum(1 for r in scored if r["health_band"] == "yellow")
    red = sum(1 for r in scored if r["health_band"] == "red")

    if args.json:
        payload = {
            "day": day,
            "as_of": as_of,
            "health_distribution": {"green": green, "yellow": yellow, "red": red},
            "accounts": scored,
        }
        if day > 0:
            base_scored = _score_book(base_book, SEED_DATE)
            base_bands = {r["account_id"]: r["health_band"] for r in base_scored}
            changes = []
            for r in scored:
                old = base_bands.get(r["account_id"])
                if old and old != r["health_band"]:
                    changes.append({
                        "account": r["name"],
                        "from_band": old,
                        "to_band": r["health_band"],
                    })
            payload["changes_from_day_0"] = changes
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("=" * 60)
    print(f"Day {day} — Book of Business Sweep")
    print("=" * 60)
    print()
    print("Health Distribution:")
    print(f"  Green:  {green}")
    print(f"  Yellow: {yellow}")
    print(f"  Red:    {red}")
    print()

    print("Top 5 Priority Accounts:")
    for i, r in enumerate(scored[:5], 1):
        arr_str = f"${r['arr_cents'] / 100:,.0f}"
        factors = ", ".join(r["priority_factors"][:4]) if r["priority_factors"] else "none"
        print(
            f"  {i}. {r['name']:35s}  score={r['priority_score']:3d}"
            f"  band={r['health_band']:6s}  ARR={arr_str}"
        )
        print(f"     Factors: {factors}")
    print()

    print("Accounts by Health Band:")
    for band in ("red", "yellow"):
        band_accounts = [r for r in scored if r["health_band"] == band]
        if band_accounts:
            print(f"  {band.upper()}:")
            for r in band_accounts:
                drivers = ", ".join(r["health_drivers"][:3]) if r["health_drivers"] else "none"
                print(f"    - {r['name']}: score={r['priority_score']}, drivers: {drivers}")
    print()

    if day > 0:
        base_scored = _score_book(base_book, SEED_DATE)
        base_bands = {r["account_id"]: r["health_band"] for r in base_scored}
        print(f"Changes from Day 0:")
        print("  Health Band Changes:")
        any_changes = False
        for r in scored:
            old = base_bands.get(r["account_id"])
            if old and old != r["health_band"]:
                print(f"    - {r['name']}: {old} -> {r['health_band']}")
                any_changes = True
        if not any_changes:
            print("    (none)")

        print("  New Risks Detected:")
        base_factors = {}
        for r in base_scored:
            base_factors[r["account_id"]] = set(r["priority_factors"])
        any_risks = False
        for r in scored:
            old_f = base_factors.get(r["account_id"], set())
            new_f = set(r["priority_factors"]) - old_f
            if new_f:
                print(f"    - {r['name']}: {', '.join(sorted(new_f))}")
                any_risks = True
        if not any_risks:
            print("    (none)")

    return 0


def _demo_timeline(args: argparse.Namespace) -> int:
    from ultra_csm.data_plane.book_simulator import simulate_book
    from ultra_csm.data_plane.synthetic_book import SEED_DATE

    use_deep = getattr(args, "deep", False)
    base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
    timeline_days = [0, 30, 60, 90, 120, 180, 270, 365]
    base_book = build_synthetic_book()

    snapshots: dict[int, dict[str, Any]] = {}
    all_scored: dict[int, list[dict[str, Any]]] = {}

    for day in timeline_days:
        as_of = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
        if day == 0:
            data = base_book
        else:
            data = simulate_book(base_book, day_offset=day)
            if use_deep:
                data = _apply_deep_data_overlay(data, day)
        scored = _score_book(data, as_of)
        all_scored[day] = scored

        green = sum(1 for r in scored if r["health_band"] == "green")
        yellow = sum(1 for r in scored if r["health_band"] == "yellow")
        red = sum(1 for r in scored if r["health_band"] == "red")
        top_priority = [
            {"name": r["name"], "score": r["priority_score"], "band": r["health_band"]}
            for r in scored[:10]
        ]
        snapshots[day] = {
            "green": green,
            "yellow": yellow,
            "red": red,
            "top_priority": top_priority,
        }

    # Compute health transitions (compare each day to day 0)
    base_bands = {r["account_id"]: r["health_band"] for r in all_scored[0]}
    base_names = {r["account_id"]: r["name"] for r in all_scored[0]}
    transitions: list[dict[str, Any]] = []
    seen_transitions: set[str] = set()

    for day in timeline_days[1:]:
        for r in all_scored[day]:
            aid = r["account_id"]
            old_band = base_bands.get(aid)
            if old_band and old_band != r["health_band"] and aid not in seen_transitions:
                transitions.append({
                    "account": r["name"],
                    "from_band": old_band,
                    "to_band": r["health_band"],
                    "first_detected_day": day,
                })
                seen_transitions.add(aid)

    # Detection timeline: new factors appearing at each day vs day 0
    base_factors_by_account: dict[str, set[str]] = {}
    for r in all_scored[0]:
        base_factors_by_account[r["account_id"]] = set(r["priority_factors"])

    day_events: dict[int, list[str]] = {d: [] for d in timeline_days}
    first_risk_detected: dict[str, int] = {}

    for day in timeline_days[1:]:
        for r in all_scored[day]:
            aid = r["account_id"]
            old_f = base_factors_by_account.get(aid, set())
            new_f = set(r["priority_factors"]) - old_f
            if new_f:
                for f in sorted(new_f):
                    desc = f"{r['name']}: {f}"
                    day_events[day].append(desc)
                if aid not in first_risk_detected:
                    first_risk_detected[aid] = day

    # Detection metrics: for accounts with detected risks and renewal dates
    detection_metrics: list[dict[str, Any]] = []
    for day in timeline_days[1:]:
        for r in all_scored[day]:
            aid = r["account_id"]
            if aid in first_risk_detected and first_risk_detected[aid] == day:
                renewal = r.get("renewal_date")
                if renewal:
                    try:
                        renewal_dt = datetime.strptime(renewal, "%Y-%m-%d")
                        detected_dt = base_date + timedelta(days=day)
                        lead_days = (renewal_dt - detected_dt).days
                        detection_metrics.append({
                            "account": r["name"],
                            "risk_type": ", ".join(
                                sorted(set(r["priority_factors"]) - base_factors_by_account.get(aid, set()))
                            ),
                            "first_detected_day": day,
                            "event_date": renewal,
                            "lead_time_days": lead_days,
                        })
                    except ValueError:
                        pass

    # Build JSON output
    json_payload = {
        "timeline_days": timeline_days,
        "snapshots": {str(d): snapshots[d] for d in timeline_days},
        "health_transitions": transitions,
        "detection_metrics": detection_metrics,
    }

    # Write timeline JSON to eval/
    repo_root = Path(__file__).resolve().parents[2]
    eval_dir = repo_root / "eval"
    eval_dir.mkdir(exist_ok=True)
    out_path = eval_dir / "demo_timeline_results.json"
    out_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(json_payload, indent=2, sort_keys=True))
        return 0

    print("=" * 60)
    print("DEMO TIMELINE — System Response Over 365 Days")
    print("=" * 60)
    print()

    for day in timeline_days:
        s = snapshots[day]
        print(f"Day {day:2d}: {s['green']} green / {s['yellow']} yellow / {s['red']} red")
    print()

    print("Health Band Transitions:")
    if transitions:
        for t in transitions:
            print(
                f"  {t['account']:35s} {t['from_band']} -> {t['to_band']}"
                f"  (day {t['first_detected_day']})"
            )
    else:
        print("  (none)")
    print()

    print("Detection Timeline:")
    for day in timeline_days:
        events = day_events.get(day, [])
        if events:
            for event in events:
                print(f"  Day {day:2d}: {event}")
    print()

    print("Risk Detection Metrics:")
    if detection_metrics:
        for m in detection_metrics:
            print(
                f"  {m['account']}: risk first detected at day {m['first_detected_day']},"
                f" renewal at {m['event_date']}"
            )
            print(f"    -> {m['lead_time_days']} days before renewal")
    else:
        print("  (none)")

    print()
    print(f"Timeline results written to {out_path}")
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

    demo_sweep = sub.add_parser("demo-sweep", help="Score book of business at a given simulation day")
    demo_sweep.add_argument("--day", type=int, default=0, help="Simulation day offset (default 0)")
    demo_sweep.add_argument("--deep", action="store_true",
                            help="Use deep data simulation (per-user activity, feature adoption, case lifecycles)")
    demo_sweep.add_argument("--json", action="store_true")
    demo_sweep.set_defaults(func=_demo_sweep)

    demo_timeline = sub.add_parser("demo-timeline", help="Run scoring across 365-day timeline")
    demo_timeline.add_argument("--deep", action="store_true",
                               help="Use deep data simulation for all timeline snapshots")
    demo_timeline.add_argument("--json", action="store_true")
    demo_timeline.set_defaults(func=_demo_timeline)

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
