"""Product telemetry simulated connector onboarding vertical.

This uses the real OTel-shaped explorer and source-map freeze machinery against
an in-memory fake OTLP transport built from the synthetic customer book's usage
signals. The output is an onboarding/readiness artifact only; it is not live
tenant proof.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.readiness import SourceReadiness, readiness_report
from ultra_csm.data_plane.source_mapping import (
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATIONS_PATH = REPO / "eval" / "product_telemetry_simulated_confirmations.json"
DEFAULT_OUTPUT = REPO / "eval" / "product_telemetry_simulated_onboarding.json"
OTLP_ENDPOINT = "https://ultra-csm-simulated-collector.internal/v1/metrics"
CATALOG_URL = "https://ultra-csm-simulated-collector.internal/catalog/metrics"


class FakeTelemetryClient:
    """In-memory OTLP-shaped transport for the connector explorer."""

    def __init__(self, catalog: dict[str, Any]) -> None:
        self.catalog = catalog
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if req.url == OTLP_ENDPOINT:
            return HttpResponse(status=200, body=b"{}", headers={"content-type": "application/json"})
        if req.url == CATALOG_URL:
            return HttpResponse(
                status=200,
                body=json.dumps(self.catalog, sort_keys=True).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        return HttpResponse(status=404, body=b"{}", headers={"content-type": "application/json"})


def build_product_telemetry_simulated_onboarding_artifact(
    *,
    confirmations_path: Path = DEFAULT_CONFIRMATIONS_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    book = build_synthetic_book()
    catalog = build_product_telemetry_fixture_catalog(book)

    no_cred_client = FakeTelemetryClient(catalog)
    missing = run_explorer("product_telemetry", env={}, client=no_cred_client)
    fake_client = FakeTelemetryClient(catalog)
    discovered = run_explorer(
        "product_telemetry",
        env={
            "OTEL_EXPORTER_OTLP_ENDPOINT": OTLP_ENDPOINT,
            "ULTRA_CSM_TELEMETRY_CATALOG_URL": CATALOG_URL,
        },
        client=fake_client,
    )
    if not discovered.ok or discovered.snapshot is None or discovered.mapping_proposal is None:
        raise RuntimeError(f"Product telemetry simulated discovery failed: {discovered.errors}")

    confirmations = load_mapping_confirmations(confirmations_path)
    _validate_confirmation_fixture(discovered, confirmations)
    frozen = freeze_confirmed_source_map(
        discovered.mapping_proposal,
        confirmations=confirmations,
    )
    sim_readiness = SourceReadiness(
        connector_id="product_telemetry",
        mode="fixture",
        state="fixture_verified",
        connected=False,
        rails_degraded=_unknown_contracts(frozen.unknown_fields),
        required_operator_actions=(
            "connect a live OTLP endpoint before any live readiness claim",
            "resource-attribute discovery resolves identity/join fields (account, grain, "
            "metric name, source ref); per-datapoint value fields (value, unit, "
            "observed_at) live in the OTLP metric payload itself and require a live "
            "sample capture, not just attribute introspection, to map",
        ),
        evidence=(
            "synthetic_customer_book",
            "fake_telemetry_client",
            "telemetry_explorer_parser",
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
        "artifact": "product_telemetry_simulated_onboarding",
        "generated_by": "eval.product_telemetry_simulated_onboarding",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
        },
        "measurement_scope": (
            "OTel required-attribute discovery, optional metric-catalog discovery, "
            "source-map proposal, deterministic confirmation, freeze, and readiness "
            "artifact over synthetic data and fake transport."
        ),
        "source_book": {
            "source": "src/ultra_csm/data_plane/synthetic_book.py",
            "accounts": len(book.accounts),
            "usage_signals": len(book.usage_signals),
            "entitlements": len(book.entitlements),
        },
        "credential_boundary": {
            "missing_env": list(missing.missing_env),
            "missing_credentials_state": missing.readiness.state,
            "requests_without_credentials": len(no_cred_client.requests),
            "transport": "FakeTelemetryClient",
            "simulated_credentials_used": True,
            "live_credentials_used": False,
            "live_tenant_proof": False,
        },
        "fixture_payload": {
            "otlp_endpoint": OTLP_ENDPOINT,
            "catalog_url": CATALOG_URL,
            "catalog_metrics_available": len(catalog["metrics"]),
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
        "readiness": asdict(sim_readiness),
        "readiness_report": readiness_report((sim_readiness,)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def build_product_telemetry_fixture_catalog(book: FixtureCustomerData) -> dict[str, Any]:
    units = {signal.metric_name: signal.unit for signal in book.usage_signals}
    return {
        "metrics": [
            {"name": metric_name, "unit": unit}
            for metric_name, unit in sorted(units.items())
        ]
    }


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


def _discovery_summary(result: ExplorerResult, client: FakeTelemetryClient) -> dict[str, Any]:
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
    artifact = build_product_telemetry_simulated_onboarding_artifact(
        confirmations_path=args.confirmations,
        output_path=args.output,
    )
    print(json.dumps({
        "artifact": _display_path(args.output),
        "fixture_state": artifact["readiness"]["state"],
        "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
        "config_hash": artifact["frozen_source_map"]["config_hash"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
