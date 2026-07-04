"""Loopway Attio simulated connector onboarding vertical (Universe v2,
WS-Tenant-Loopway, Wave 3). Mirrors ``eval/attio_simulated_onboarding.py``
exactly (same explorer/source-map machinery, same fixture-vs-live claim
boundary) but points the fake Attio transport at Loopway's own
400-account book (``src/ultra_csm/data_plane/tenants/loopway/
attio_transport.py``) instead of fleetops'. This is the mapping layer's
THIRD metadata dialect (fleetops=Salesforce-shaped, fieldstone=HubSpot-
shaped per the sibling workstream, loopway=Attio-shaped) -- the record
here is the question count this dialect produces, per the dispatch's
"record the question count (third data point)" instruction.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.readiness import SourceReadiness, readiness_report
from ultra_csm.data_plane.source_mapping import (
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.tenants.loopway.attio_transport import (
    FakeLoopwayAttioClient,
    build_loopway_attio_fixture_payloads,
)
from ultra_csm.data_plane.tenants.loopway.narrative_shared import base_synthetic_book

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATIONS_PATH = REPO / "eval" / "loopway_attio_simulated_confirmations.json"
DEFAULT_OUTPUT = REPO / "eval" / "loopway_attio_simulated_onboarding.json"


def build_loopway_attio_simulated_onboarding_artifact(
    *,
    confirmations_path: Path = DEFAULT_CONFIRMATIONS_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    book = base_synthetic_book()
    payloads = build_loopway_attio_fixture_payloads(book)

    no_cred_client = FakeLoopwayAttioClient(payloads)
    missing = run_explorer("attio_crm", env={}, client=no_cred_client)
    fake_client = FakeLoopwayAttioClient(payloads)
    discovered = run_explorer(
        "attio_crm",
        env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "simulated-attio-token-loopway"},
        client=fake_client,
    )
    if not discovered.ok or discovered.snapshot is None or discovered.mapping_proposal is None:
        raise RuntimeError(f"Loopway Attio simulated discovery failed: {discovered.errors}")

    confirmations = load_mapping_confirmations(confirmations_path)
    _validate_confirmation_fixture(discovered, confirmations)
    frozen = freeze_confirmed_source_map(discovered.mapping_proposal, confirmations=confirmations)
    sim_readiness = SourceReadiness(
        connector_id="attio_crm",
        mode="fixture",
        state="fixture_verified",
        connected=False,
        rails_degraded=_unknown_contracts(frozen.unknown_fields),
        required_operator_actions=(
            "connect live Attio credentials before any live readiness claim",
            "review unknown source-map fields before customer-tenant use",
        ),
        evidence=(
            "loopway_synthetic_book",
            "fake_loopway_attio_client",
            "attio_explorer_parser",
            "frozen_source_map_config",
        ),
    )
    ambiguous_keys = sorted(
        entry.key for entry in discovered.mapping_proposal.entries if entry.state == "ambiguous_confirm"
    )
    missing_keys = sorted(
        entry.key for entry in discovered.mapping_proposal.entries if entry.state == "missing_to_unknown"
    )
    artifact = {
        "artifact": "loopway_attio_simulated_onboarding",
        "generated_by": "eval.loopway_attio_simulated_onboarding",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
        },
        "measurement_scope": (
            "Attio discovery, source-map proposal, deterministic confirmation, "
            "freeze, and readiness artifact over Loopway's 400-account synthetic "
            "book and fake transport -- the mapping layer's third vendor dialect "
            "(fleetops=Salesforce-shaped, loopway=Attio-shaped)."
        ),
        "source_book": {
            "source": "src/ultra_csm/data_plane/tenants/loopway/synthetic_book.py",
            "accounts": len(book.accounts),
            "contacts": len(book.contacts),
        },
        "credential_boundary": {
            "missing_env": list(missing.missing_env),
            "missing_credentials_state": missing.readiness.state,
            "requests_without_credentials": len(no_cred_client.requests),
            "transport": "FakeLoopwayAttioClient",
            "simulated_credentials_used": True,
            "live_credentials_used": False,
            "live_tenant_proof": False,
        },
        "discovery": _discovery_summary(discovered, fake_client),
        "mapping_proposal": {
            "proposal_hash": discovered.mapping_proposal.proposal_hash,
            "schema_hash": discovered.mapping_proposal.schema_hash,
            "coverage": discovered.mapping_proposal.coverage,
            "required_operator_actions": list(discovered.mapping_proposal.required_operator_actions),
            "ambiguous_keys": ambiguous_keys,
            "missing_to_unknown_keys": missing_keys,
        },
        "confirmation_fixture": {
            "path": _display_path(confirmations_path),
            "confirmed_keys": sorted(confirmations),
        },
        "frozen_source_map": frozen.to_dict(),
        "readiness": asdict(sim_readiness),
        "readiness_report": readiness_report((sim_readiness,)),
        "third_dialect_note": (
            f"question_count={len(ambiguous_keys)} confirmation questions on this "
            "Attio-shaped dialect at 400 accounts -- see docs/PROGRAM_REPORT_17.md "
            "for the cross-dialect comparison."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _validate_confirmation_fixture(result: ExplorerResult, confirmations: dict[str, Any]) -> None:
    assert result.mapping_proposal is not None
    ambiguous = {entry.key for entry in result.mapping_proposal.entries if entry.state == "ambiguous_confirm"}
    missing = ambiguous - set(confirmations)
    unused = set(confirmations) - {entry.key for entry in result.mapping_proposal.entries}
    if missing:
        raise RuntimeError(f"confirmation fixture missing keys: {sorted(missing)}")
    if unused:
        raise RuntimeError(f"confirmation fixture has unused keys: {sorted(unused)}")


def _unknown_contracts(unknown_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.split(".", 1)[0] for item in unknown_fields}))


def _discovery_summary(result: ExplorerResult, client: FakeLoopwayAttioClient) -> dict[str, Any]:
    assert result.snapshot is not None
    return {
        "ok": result.ok,
        "schema_hash": result.snapshot.schema_hash,
        "source_steps": list(result.snapshot.source_steps),
        "sample_counts": result.snapshot.sample_counts,
        "objects": [
            {"name": obj.name, "fields": [field.name for field in obj.fields]}
            for obj in result.snapshot.objects
            if obj.fields
        ],
        "requests_on_fake_transport": len(client.requests),
        "request_urls": [request.url for request in client.requests],
        "explorer_state_on_fake_transport": result.readiness.state,
        "explorer_connected_flag_is_not_live_proof": result.readiness.connected,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmations", type=Path, default=DEFAULT_CONFIRMATIONS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_loopway_attio_simulated_onboarding_artifact(
        confirmations_path=args.confirmations, output_path=args.output
    )
    print(json.dumps({
        "artifact": _display_path(args.output),
        "fixture_state": artifact["readiness"]["state"],
        "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
        "ambiguous_question_count": len(artifact["mapping_proposal"]["ambiguous_keys"]),
        "config_hash": artifact["frozen_source_map"]["config_hash"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
