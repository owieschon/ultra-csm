"""Connector readiness contracts for live data-plane adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ConnectorId = Literal[
    "salesforce_crm",
    "attio_crm",
    "gainsight_cs",
    "rocketlane_onboarding",
    "product_telemetry",
    "external_book",
]
ConnectorMode = Literal["fixture", "live", "disabled"]
ReadinessState = Literal[
    "fixture_verified",
    "shape_verified_pending_live_creds",
    "live_auth_verified",
    "live_schema_verified",
    "live_smoke_verified",
    "degraded",
    "disabled",
]
AuthStrategy = Literal["oauth2", "api_key", "access_key", "otlp_config"]
PaginationStrategy = Literal["offset", "cursor", "soql_next_records_url", "collector_batch", "none"]


@dataclass(frozen=True)
class OfficialDocRef:
    title: str
    url: str
    accessed_on: str


@dataclass(frozen=True)
class RecordedShape:
    name: str
    contract: str
    fixture_path: str
    docs: tuple[OfficialDocRef, ...]


@dataclass(frozen=True)
class ConnectorSpec:
    connector_id: ConnectorId
    display_name: str
    mode_env: str
    credential_env: tuple[str, ...]
    auth_strategies: tuple[AuthStrategy, ...]
    pagination: tuple[PaginationStrategy, ...]
    source_contracts: tuple[str, ...]
    discovery_surfaces: tuple[str, ...]
    recorded_shapes: tuple[RecordedShape, ...]
    smoke_command: str
    docs: tuple[OfficialDocRef, ...]


@dataclass(frozen=True)
class SourceReadiness:
    connector_id: ConnectorId
    mode: ConnectorMode
    state: ReadinessState
    connected: bool
    rails_degraded: tuple[str, ...]
    required_operator_actions: tuple[str, ...]
    evidence: tuple[str, ...] = ()


def validate_connector_spec(spec: ConnectorSpec) -> None:
    """Fail fast when a connector cannot meet the shared live-adapter bar."""

    if not spec.display_name:
        raise ValueError(f"{spec.connector_id}: display_name is required")
    if not spec.mode_env:
        raise ValueError(f"{spec.connector_id}: mode_env is required")
    if not spec.docs:
        raise ValueError(f"{spec.connector_id}: at least one official doc is required")
    if not spec.recorded_shapes:
        raise ValueError(f"{spec.connector_id}: recorded_shapes are required")
    if not spec.source_contracts:
        raise ValueError(f"{spec.connector_id}: source_contracts are required")
    if not spec.discovery_surfaces:
        raise ValueError(f"{spec.connector_id}: discovery_surfaces are required")
    if not spec.smoke_command.startswith("ucsm connectors smoke "):
        raise ValueError(f"{spec.connector_id}: smoke_command must use the shared CLI")
    for doc in (*spec.docs, *(doc for shape in spec.recorded_shapes for doc in shape.docs)):
        if not doc.url.startswith("https://"):
            raise ValueError(f"{spec.connector_id}: official docs must use HTTPS URLs")
        if not doc.accessed_on:
            raise ValueError(f"{spec.connector_id}: doc access date is required")
    for shape in spec.recorded_shapes:
        if shape.contract not in spec.source_contracts:
            raise ValueError(
                f"{spec.connector_id}: {shape.name} records {shape.contract}, "
                "but that contract is not declared"
            )
        if not shape.fixture_path.startswith("tests/fixtures/connectors/"):
            raise ValueError(
                f"{spec.connector_id}: {shape.name} fixture must live under "
                "tests/fixtures/connectors/"
            )


def validate_readiness_state(readiness: SourceReadiness, spec: ConnectorSpec) -> None:
    if readiness.connector_id != spec.connector_id:
        raise ValueError("readiness connector_id does not match spec")
    if readiness.mode == "disabled" and readiness.state != "disabled":
        raise ValueError("disabled sources must report disabled state")
    if readiness.state == "live_smoke_verified" and readiness.mode != "live":
        raise ValueError("live smoke verification requires live mode")
    if readiness.connected and readiness.mode != "live":
        raise ValueError("only live mode may report connected=True")
    if readiness.mode == "live" and spec.credential_env == ():
        raise ValueError(f"{spec.connector_id}: live mode requires credential env vars")


def readiness_report(readiness: tuple[SourceReadiness, ...]) -> dict[str, object]:
    states = {source.connector_id: source.state for source in readiness}
    degraded_rails = sorted({rail for source in readiness for rail in source.rails_degraded})
    operator_actions = tuple(
        action
        for source in readiness
        for action in source.required_operator_actions
    )
    return {
        "sources": states,
        "degraded_rails": tuple(degraded_rails),
        "required_operator_actions": operator_actions,
    }
