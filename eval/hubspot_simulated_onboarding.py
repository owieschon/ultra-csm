"""HubSpot simulated connector onboarding vertical (Universe v2,
WS-Tenant-Fieldstone, Wave 3). Mirrors
``eval.attio_simulated_onboarding``'s pattern: the real HubSpot explorer
and source-map freeze machinery against an in-memory fake HubSpot client
built from the fieldstone book. Output is an onboarding/readiness
artifact only; it is not live tenant proof.

Proves the Tier-A pluggability test the dispatch names: HubSpot's
association-schema endpoint (a separate schema surface from the
properties describe) is captured into ``DiscoveredField.references`` by
``explorer.py``'s new ``_parse_hubspot_associations_schema`` -- verified
directly below, not merely asserted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.readiness import SourceReadiness, readiness_report
from ultra_csm.data_plane.source_mapping import (
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.tenants.fieldstone.book import build_fieldstone_book
from ultra_csm.data_plane.tenants.fieldstone.hubspot_transport import (
    FakeHubSpotClient,
    build_hubspot_fixture_payloads,
)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATIONS_PATH = REPO / "eval" / "hubspot_simulated_confirmations.json"
DEFAULT_OUTPUT = REPO / "eval" / "hubspot_simulated_onboarding.json"


def build_hubspot_simulated_onboarding_artifact(
    *,
    confirmations_path: Path = DEFAULT_CONFIRMATIONS_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    book = build_fieldstone_book()
    payloads = build_hubspot_fixture_payloads(book)

    no_cred_client = FakeHubSpotClient(payloads)
    missing = run_explorer("hubspot_crm", env={}, client=no_cred_client)
    fake_client = FakeHubSpotClient(payloads)
    discovered = run_explorer(
        "hubspot_crm",
        env={"ULTRA_CSM_HUBSPOT_ACCESS_TOKEN": "simulated-hubspot-token"},
        client=fake_client,
    )
    if not discovered.ok or discovered.snapshot is None or discovered.mapping_proposal is None:
        raise RuntimeError(f"HubSpot simulated discovery failed: {discovered.errors}")

    confirmations = load_mapping_confirmations(confirmations_path)
    _validate_confirmation_fixture(discovered, confirmations)
    frozen = freeze_confirmed_source_map(
        discovered.mapping_proposal,
        confirmations=confirmations,
    )

    # The pluggability-test proof: did the explorer capture the
    # association schema's FK graph into DiscoveredField.references?
    # (The snapshot has two separate "contacts" DiscoveredObjects -- one
    # from the plain properties-describe step, one from the associations-
    # schema step -- so this checks fields across every object, not just
    # the first "contacts" match.)
    association_fields = tuple(
        field
        for obj in discovered.snapshot.objects
        for field in obj.fields
        if field.field_type == "association"
    )
    tier_a_association_capture_proven = bool(
        association_fields and all(field.references for field in association_fields)
    )

    sim_readiness = SourceReadiness(
        connector_id="hubspot_crm",
        mode="fixture",
        state="fixture_verified",
        connected=False,
        rails_degraded=_unknown_contracts(frozen.unknown_fields),
        required_operator_actions=(
            "connect live HubSpot credentials before any live readiness claim",
            "review unknown source-map fields before customer-tenant use",
        ),
        evidence=(
            "fieldstone_synthetic_book",
            "fake_hubspot_client",
            "hubspot_explorer_parser",
            "frozen_source_map_config",
        ),
    )
    ambiguous_keys = sorted(
        entry.key
        for entry in discovered.mapping_proposal.entries
        if entry.state == "ambiguous_confirm"
    )
    missing_keys = sorted(
        entry.key
        for entry in discovered.mapping_proposal.entries
        if entry.state == "missing_to_unknown"
    )
    artifact = {
        "artifact": "hubspot_simulated_onboarding",
        "generated_by": "eval.hubspot_simulated_onboarding",
        "tenant": "fieldstone",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
        },
        "measurement_scope": (
            "HubSpot discovery, source-map proposal, deterministic confirmation, "
            "freeze, and readiness artifact over fieldstone's synthetic 12-account "
            "book and fake transport."
        ),
        "pluggability_test": {
            "claim": (
                "HubSpot declares its contact<->company FK graph via a SEPARATE "
                "associations-schema endpoint, not a lookup field on the properties "
                "describe (unlike Salesforce's referenceTo, or Attio's attributes "
                "describe, neither of which surfaces this the same way). A Tier-A "
                "parser reading only the properties-describe response would miss it "
                "entirely."
            ),
            "tier_a_association_capture_proven": tier_a_association_capture_proven,
            "association_fields_discovered": [
                {"name": f.name, "references": list(f.references), "relationship_name": f.relationship_name}
                for f in association_fields
            ],
        },
        "source_book": {
            "source": "src/ultra_csm/data_plane/tenants/fieldstone/book.py",
            "accounts": len(book.accounts),
            "contacts": len(book.contacts),
        },
        "credential_boundary": {
            "missing_env": list(missing.missing_env),
            "missing_credentials_state": missing.readiness.state,
            "requests_without_credentials": len(no_cred_client.requests),
            "transport": "FakeHubSpotClient",
            "simulated_credentials_used": True,
            "live_credentials_used": False,
            "live_tenant_proof": False,
        },
        "discovery": _discovery_summary(discovered, fake_client),
        "mapping_proposal": {
            "proposal_hash": discovered.mapping_proposal.proposal_hash,
            "schema_hash": discovered.mapping_proposal.schema_hash,
            "coverage": discovered.mapping_proposal.coverage,
            "required_operator_actions": list(
                discovered.mapping_proposal.required_operator_actions
            ),
            "ambiguous_keys": ambiguous_keys,
            "missing_to_unknown_keys": missing_keys,
        },
        "confirmation_fixture": {
            "path": _display_path(confirmations_path),
            "confirmed_keys": sorted(confirmations),
        },
        "frozen_source_map": frozen.to_dict(),
        "readiness": _asdict_readiness(sim_readiness),
        "readiness_report": readiness_report((sim_readiness,)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _asdict_readiness(readiness: SourceReadiness) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(readiness)


def _validate_confirmation_fixture(
    result: ExplorerResult,
    confirmations: dict[str, Any],
) -> None:
    assert result.mapping_proposal is not None
    ambiguous = {
        entry.key
        for entry in result.mapping_proposal.entries
        if entry.state == "ambiguous_confirm"
    }
    missing = ambiguous - set(confirmations)
    unused = set(confirmations) - {
        entry.key for entry in result.mapping_proposal.entries
    }
    if missing:
        raise RuntimeError(f"confirmation fixture missing keys: {sorted(missing)}")
    if unused:
        raise RuntimeError(f"confirmation fixture has unused keys: {sorted(unused)}")


def _unknown_contracts(unknown_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.split(".", 1)[0] for item in unknown_fields}))


def _discovery_summary(result: ExplorerResult, client: FakeHubSpotClient) -> dict[str, Any]:
    assert result.snapshot is not None
    return {
        "ok": result.ok,
        "schema_hash": result.snapshot.schema_hash,
        "source_steps": list(result.snapshot.source_steps),
        "sample_counts": result.snapshot.sample_counts,
        "objects": [
            {
                "name": obj.name,
                "fields": [field.name for field in obj.fields],
            }
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
    artifact = build_hubspot_simulated_onboarding_artifact(
        confirmations_path=args.confirmations,
        output_path=args.output,
    )
    print(json.dumps({
        "artifact": _display_path(args.output),
        "fixture_state": artifact["readiness"]["state"],
        "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
        "config_hash": artifact["frozen_source_map"]["config_hash"],
        "tier_a_association_capture_proven": artifact["pluggability_test"]["tier_a_association_capture_proven"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
