"""Schema-snapshot to source-map proposal for connector onboarding.

Discovery tells us what fields exist. This module turns that snapshot into a
reviewable mapping proposal: deterministic matches are mapped, ambiguous custom
or tenant-specific fields are routed to human confirmation, and missing fields
degrade to unknown instead of being guessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, Mapping

from ultra_csm.data_plane.connector_catalog import CONNECTOR_SPECS
from ultra_csm.data_plane.explorer import DiscoveredField, DiscoveredObject, SchemaSnapshot
from ultra_csm.data_plane.readiness import ConnectorId
from ultra_csm.data_plane.source_maps import (
    ALL_SOURCE_MAPS,
    EXTERNAL_BOOK_SOURCE_MAPS,
    SourceField,
    SourceObjectMap,
)


MappingState = Literal["mapped", "ambiguous_confirm", "missing_to_unknown"]
MappingVerdict = Literal["mapped", "not_mappable"]
ValueDirection = Literal[
    "not_applicable",
    "higher_is_better",
    "lower_is_better",
    "ordered_confirm",
    "direction_confirm",
]
_VALUE_DIRECTIONS = {
    "not_applicable",
    "higher_is_better",
    "lower_is_better",
    "ordered_confirm",
    "direction_confirm",
}


@dataclass(frozen=True)
class MappingCandidateEvidence:
    source_object: str
    source_field: str
    source_path: str
    rows_present: int
    rows_nonempty: int
    rows_sampled: int
    field_type: str
    confidence: float
    reason: str
    value_shape: str = ""
    distinct_count: int = 0


@dataclass(frozen=True)
class ProposedFieldMapping:
    connector_id: ConnectorId
    contract: str
    internal_field: str
    source_object: str | None
    source_field: str | None
    source_path: str | None
    state: MappingState
    semantic_role: str
    value_direction: ValueDirection
    requires_human_confirmation: bool
    confidence: float
    reason: str
    pii: str
    llm_allowed: bool
    candidate_evidence: tuple[MappingCandidateEvidence, ...] = ()
    # A declared value transform applied at ingest time, from a closed enum
    # (see VALUE_TRANSFORMS). "none" is the identity; it is omitted from the
    # serialized form so configs without a transform hash byte-identically to
    # pre-2C configs.
    transform: str = "none"

    @property
    def key(self) -> str:
        return f"{self.contract}.{self.internal_field}"

    def to_dict(self) -> dict:
        data = asdict(self)
        if data.get("transform") == "none":
            data.pop("transform", None)
        return data


@dataclass(frozen=True)
class SourceMapProposal:
    connector_id: ConnectorId
    schema_hash: str
    proposal_hash: str
    entries: tuple[ProposedFieldMapping, ...]
    coverage: dict[str, int]
    required_operator_actions: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "schema_hash": self.schema_hash,
            "proposal_hash": self.proposal_hash,
            "entries": [entry.to_dict() for entry in self.entries],
            "coverage": self.coverage,
            "required_operator_actions": self.required_operator_actions,
        }


@dataclass(frozen=True)
class MappingConfirmation:
    contract: str
    internal_field: str
    source_object: str | None = None
    source_field: str | None = None
    source_path: str | None = None
    semantic_role: str | None = None
    value_direction: ValueDirection = "not_applicable"
    verdict: MappingVerdict = "mapped"
    # None => inherit the internal field's default transform (see
    # DEFAULT_FIELD_TRANSFORMS). A string overrides it, from VALUE_TRANSFORMS.
    transform: str | None = None


# The closed set of declared value transforms. Growth requires a design
# conversation, not a config edit -- an unknown transform fails validation.
VALUE_TRANSFORMS = ("none", "currency_to_cents")

# Transform a contract's internal field carries by default because the field's
# semantics require it (an amount stored as integer cents). Declared once, in
# one place, rather than hardcoded in the ingest path -- so it is visible and
# auditable in the frozen config.
DEFAULT_FIELD_TRANSFORMS = {"amount_cents": "currency_to_cents"}


@dataclass(frozen=True)
class FrozenSourceMapConfig:
    connector_id: ConnectorId
    schema_hash: str
    proposal_hash: str
    config_hash: str
    mappings: tuple[ProposedFieldMapping, ...]
    unknown_fields: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "schema_hash": self.schema_hash,
            "proposal_hash": self.proposal_hash,
            "config_hash": self.config_hash,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
            "unknown_fields": self.unknown_fields,
        }


def propose_source_mapping(snapshot: SchemaSnapshot) -> SourceMapProposal:
    spec = CONNECTOR_SPECS[snapshot.connector_id]
    discovered = _object_index(snapshot.objects)
    entries: list[ProposedFieldMapping] = []

    for contract in spec.source_contracts:
        source_map = _source_map_for(snapshot.connector_id, contract)
        if source_map is None:
            continue
        source_object = _find_object(discovered, source_map.object_name)
        for internal_field, source_field in source_map.fields.items():
            entries.append(
                _propose_field(
                    snapshot.connector_id,
                    contract,
                    internal_field,
                    source_field,
                    source_object,
                )
            )

    entries.extend(_custom_field_suggestions(snapshot.connector_id, snapshot.objects, entries))
    coverage = _coverage(entries)
    actions = _operator_actions(entries)
    proposal_hash = _proposal_hash(snapshot.connector_id, snapshot.schema_hash, entries)
    return SourceMapProposal(
        connector_id=snapshot.connector_id,
        schema_hash=snapshot.schema_hash,
        proposal_hash=proposal_hash,
        entries=tuple(entries),
        coverage=coverage,
        required_operator_actions=actions,
    )


def freeze_confirmed_source_map(
    proposal: SourceMapProposal,
    *,
    confirmations: Mapping[str, MappingConfirmation] | None = None,
) -> FrozenSourceMapConfig:
    confirmations = confirmations or {}
    frozen: list[ProposedFieldMapping] = []
    unknown: list[str] = []

    for entry in proposal.entries:
        if entry.state == "mapped":
            frozen.append(entry)
            continue
        if entry.state == "missing_to_unknown":
            unknown.append(entry.key)
            continue
        confirmation = confirmations.get(entry.key)
        if confirmation is None:
            raise ValueError(f"{entry.key} requires human confirmation")
        if confirmation.verdict == "not_mappable":
            unknown.append(entry.key)
            continue
        frozen.append(_confirmed(entry, confirmation))

    config_hash = _frozen_config_hash(proposal.proposal_hash, frozen, unknown)
    config = FrozenSourceMapConfig(
        connector_id=proposal.connector_id,
        schema_hash=proposal.schema_hash,
        proposal_hash=proposal.proposal_hash,
        config_hash=config_hash,
        mappings=tuple(frozen),
        unknown_fields=tuple(sorted(unknown)),
    )
    validate_frozen_source_map_config(config)
    return config


def load_frozen_source_map_config(path: str | Path) -> FrozenSourceMapConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source-map config must be a JSON object")
    config = _config_from_payload(payload)
    validate_frozen_source_map_config(config)
    return config


def load_source_map_proposal(path: str | Path) -> SourceMapProposal:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source-map proposal must be a JSON object")
    return _proposal_from_payload(payload)


def load_mapping_confirmations(path: str | Path) -> dict[str, MappingConfirmation]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("mapping confirmations must be a JSON object")
    confirmations = payload.get("confirmations", payload)
    if not isinstance(confirmations, dict):
        raise ValueError("mapping confirmations must be keyed by field")
    return {
        str(key): _confirmation_from_payload(value)
        for key, value in confirmations.items()
    }


def validate_frozen_source_map_config(config: FrozenSourceMapConfig) -> None:
    if config.connector_id not in CONNECTOR_SPECS:
        raise ValueError(f"{config.connector_id}: unknown connector_id")
    for mapping in config.mappings:
        if mapping.state != "mapped" or mapping.requires_human_confirmation:
            raise ValueError(f"{mapping.key} is not confirmed for runtime use")
        if mapping.value_direction in {"ordered_confirm", "direction_confirm"}:
            raise ValueError(f"{mapping.key} still has unresolved value direction")
        if not mapping.source_object or not mapping.source_field or not mapping.source_path:
            raise ValueError(f"{mapping.key} is missing source coordinates")
        if mapping.transform not in VALUE_TRANSFORMS:
            raise ValueError(f"{mapping.key} has unknown transform {mapping.transform!r}")
    expected = _frozen_config_hash(
        config.proposal_hash,
        list(config.mappings),
        list(config.unknown_fields),
    )
    if config.config_hash != expected:
        raise ValueError("source-map config_hash does not match config contents")


def _propose_field(
    connector_id: ConnectorId,
    contract: str,
    internal_field: str,
    source_field: SourceField,
    source_object: DiscoveredObject | None,
) -> ProposedFieldMapping:
    semantic_role = _semantic_role(contract, internal_field)
    direction = _value_direction(contract, internal_field)
    needs_direction_confirm = direction != "not_applicable"
    if source_object is None:
        return _entry(
            connector_id,
            contract,
            internal_field,
            source_object=None,
            source_field=None,
            source_path=None,
            state="missing_to_unknown",
            semantic_role=semantic_role,
            value_direction=direction,
            requires_confirmation=False,
            confidence=0.0,
            reason="source object not discovered",
            source=source_field,
        )

    discovered_field = _find_field(source_object, source_field.api_name)
    if discovered_field is None:
        return _entry(
            connector_id,
            contract,
            internal_field,
            source_object=source_object.name,
            source_field=None,
            source_path=None,
            state="missing_to_unknown",
            semantic_role=semantic_role,
            value_direction=direction,
            requires_confirmation=False,
            confidence=0.0,
            reason=f"{source_field.api_name} not present in discovered schema",
            source=source_field,
        )

    if not source_field.standard or needs_direction_confirm:
        reason = "custom or tenant-specific field requires confirmation"
        if needs_direction_confirm:
            reason = "value direction affects scoring and requires confirmation"
        return _entry(
            connector_id,
            contract,
            internal_field,
            source_object=source_object.name,
            source_field=discovered_field.name,
            source_path=discovered_field.source_path,
            state="ambiguous_confirm",
            semantic_role=semantic_role,
            value_direction=direction,
            requires_confirmation=True,
            confidence=0.91 if source_field.standard and not discovered_field.custom else 0.58,
            reason=reason,
            source=source_field,
        )

    return _entry(
        connector_id,
        contract,
        internal_field,
        source_object=source_object.name,
        source_field=discovered_field.name,
        source_path=discovered_field.source_path,
        state="mapped",
        semantic_role=semantic_role,
        value_direction=direction,
        requires_confirmation=False,
        confidence=0.95,
        reason="deterministic standard-field match",
        source=source_field,
    )


def _custom_field_suggestions(
    connector_id: ConnectorId,
    objects: tuple[DiscoveredObject, ...],
    existing: list[ProposedFieldMapping],
) -> tuple[ProposedFieldMapping, ...]:
    known = {
        (_norm(entry.source_object or ""), _norm(entry.source_field or ""))
        for entry in existing
        if entry.source_object and entry.source_field
    }
    suggestions = []
    for obj in objects:
        for field in obj.fields:
            if not field.custom:
                continue
            if (_norm(obj.name), _norm(field.name)) in known:
                continue
            role = _suggest_semantic_role(field.name)
            if role == "unclassified":
                continue
            suggestions.append(
                ProposedFieldMapping(
                    connector_id=connector_id,
                    contract="__tenant_custom__",
                    internal_field=_snake(field.name),
                    source_object=obj.name,
                    source_field=field.name,
                    source_path=field.source_path,
                    state="ambiguous_confirm",
                    semantic_role=role,
                    value_direction=(
                        "direction_confirm"
                        if role in {"health_signal", "activation_signal", "sentiment_signal"}
                        else "not_applicable"
                    ),
                    requires_human_confirmation=True,
                    confidence=0.42,
                    reason="custom field semantic-role suggestion; not used until confirmed",
                    pii="none",
                    llm_allowed=True,
                )
            )
    return tuple(suggestions)


def _source_map_for(connector_id: ConnectorId, contract: str) -> SourceObjectMap | None:
    if connector_id in {"salesforce_crm", "gainsight_cs"}:
        return ALL_SOURCE_MAPS.get(contract)
    if connector_id == "product_telemetry":
        return _TELEMETRY_SOURCE_MAPS.get(contract)
    if connector_id == "attio_crm":
        return _ATTIO_SOURCE_MAPS.get(contract)
    if connector_id == "rocketlane_onboarding":
        return _ROCKETLANE_SOURCE_MAPS.get(contract)
    if connector_id == "external_book":
        return EXTERNAL_BOOK_SOURCE_MAPS.get(contract)
    return None


def _object_index(objects: tuple[DiscoveredObject, ...]) -> dict[str, DiscoveredObject]:
    return {_norm(obj.name): obj for obj in objects if obj.fields}


def _find_object(index: dict[str, DiscoveredObject], object_name: str) -> DiscoveredObject | None:
    candidates = {_norm(object_name)}
    if "/" in object_name:
        candidates.update(_norm(part) for part in object_name.split("/"))
    for candidate in candidates:
        if candidate in index:
            return index[candidate]
    return None


def _find_field(obj: DiscoveredObject, api_name: str) -> DiscoveredField | None:
    target = _norm(api_name)
    for field in obj.fields:
        if _norm(field.name) == target:
            return field
    return None


def _entry(
    connector_id: ConnectorId,
    contract: str,
    internal_field: str,
    *,
    source_object: str | None,
    source_field: str | None,
    source_path: str | None,
    state: MappingState,
    semantic_role: str,
    value_direction: ValueDirection,
    requires_confirmation: bool,
    confidence: float,
    reason: str,
    source: SourceField,
) -> ProposedFieldMapping:
    return ProposedFieldMapping(
        connector_id=connector_id,
        contract=contract,
        internal_field=internal_field,
        source_object=source_object,
        source_field=source_field,
        source_path=source_path,
        state=state,
        semantic_role=semantic_role,
        value_direction=value_direction,
        requires_human_confirmation=requires_confirmation,
        confidence=confidence,
        reason=reason,
        pii=source.pii,
        llm_allowed=source.llm_allowed,
        candidate_evidence=(
            (
                _candidate_from_field(
                    source_object,
                    source_field,
                    source_path,
                    confidence,
                    reason,
                ),
            )
            if source_object and source_field and source_path
            else ()
        ),
    )


def _confirmed(
    entry: ProposedFieldMapping,
    confirmation: MappingConfirmation,
) -> ProposedFieldMapping:
    if (
        not confirmation.source_object
        or not confirmation.source_field
        or not confirmation.source_path
    ):
        raise ValueError(f"{entry.key} mapped confirmation requires source coordinates")
    value_direction = _confirmed_value_direction(entry, confirmation)
    return ProposedFieldMapping(
        connector_id=entry.connector_id,
        contract=entry.contract,
        internal_field=entry.internal_field,
        source_object=confirmation.source_object,
        source_field=confirmation.source_field,
        source_path=confirmation.source_path,
        state="mapped",
        semantic_role=confirmation.semantic_role or entry.semantic_role,
        value_direction=value_direction,
        requires_human_confirmation=False,
        confidence=1.0,
        reason="human-confirmed mapping frozen into deterministic config",
        pii=entry.pii,
        llm_allowed=entry.llm_allowed,
        candidate_evidence=entry.candidate_evidence,
        transform=_resolved_transform(entry.internal_field, confirmation.transform),
    )


def _resolved_transform(internal_field: str, override: str | None) -> str:
    transform = override if override is not None else DEFAULT_FIELD_TRANSFORMS.get(
        internal_field, "none"
    )
    if transform not in VALUE_TRANSFORMS:
        raise ValueError(
            f"unknown transform {transform!r}; allowed: {', '.join(VALUE_TRANSFORMS)}"
        )
    return transform


def _confirmed_value_direction(
    entry: ProposedFieldMapping,
    confirmation: MappingConfirmation,
) -> ValueDirection:
    if entry.value_direction == "not_applicable":
        return confirmation.value_direction
    if confirmation.value_direction in {
        "not_applicable",
        "ordered_confirm",
        "direction_confirm",
    }:
        raise ValueError(f"{entry.key} requires explicit value direction confirmation")
    return confirmation.value_direction


def _coverage(entries: list[ProposedFieldMapping]) -> dict[str, int]:
    counts = {"mapped": 0, "ambiguous_confirm": 0, "missing_to_unknown": 0}
    for entry in entries:
        counts[entry.state] += 1
    counts["total"] = len(entries)
    return counts


def _operator_actions(entries: list[ProposedFieldMapping]) -> tuple[str, ...]:
    ambiguous = sorted(entry.key for entry in entries if entry.state == "ambiguous_confirm")
    missing = sorted(entry.key for entry in entries if entry.state == "missing_to_unknown")
    actions = []
    if ambiguous:
        actions.append(f"confirm {len(ambiguous)} semantic/value mappings")
    if missing:
        actions.append(f"review {len(missing)} missing fields; affected rails remain unknown")
    return tuple(actions)


def _semantic_role(contract: str, internal_field: str) -> str:
    name = f"{contract}.{internal_field}"
    if internal_field in {
        "account_id",
        "company_id",
        "contact_id",
        "signal_id",
        "plan_id",
        "cta_id",
    }:
        return "identity_join"
    if internal_field in {
        "renewal_date",
        "close_date",
        "target_date",
        "due_date",
        "expected_by",
        "achieved_at",
    }:
        return "time_boundary"
    if internal_field in {"score", "current_score", "band", "drivers"}:
        return "health_signal"
    if internal_field in {
        "active_users",
        "active_assets",
        "adoption_rate",
        "underused_capabilities",
        "value",
    }:
        return "adoption_signal"
    if name.startswith("TimeToValueMilestone."):
        return "activation_milestone"
    if internal_field in {"objectives", "status"} and contract == "SuccessPlan":
        return "outcome_plan"
    if internal_field in {"summary", "subject"}:
        return "customer_content"
    return "context"


def _value_direction(contract: str, internal_field: str) -> ValueDirection:
    if internal_field in {
        "current_score",
        "score",
        "adoption_rate",
        "active_users",
        "active_assets",
    }:
        return "direction_confirm"
    if internal_field in {"priority", "band", "stage_name", "status"}:
        return "ordered_confirm"
    if contract == "TimeToValueMilestone" and internal_field in {"expected_by", "achieved_at"}:
        return "lower_is_better"
    return "not_applicable"


def _suggest_semantic_role(field_name: str) -> str:
    norm = _norm(field_name)
    if any(token in norm for token in ("health", "score", "risk")):
        return "health_signal"
    if any(token in norm for token in ("activation", "golive", "live", "onboarding")):
        return "activation_signal"
    if "sentiment" in norm or "engagement" in norm:
        return "sentiment_signal"
    if "renewal" in norm:
        return "time_boundary"
    return "unclassified"


def _proposal_hash(
    connector_id: ConnectorId,
    schema_hash: str,
    entries: list[ProposedFieldMapping],
) -> str:
    payload = {
        "connector_id": connector_id,
        "schema_hash": schema_hash,
        "entries": [entry.to_dict() for entry in entries],
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _frozen_config_hash(
    proposal_hash: str,
    frozen: list[ProposedFieldMapping],
    unknown: list[str],
) -> str:
    payload = {
        "proposal_hash": proposal_hash,
        "mappings": [entry.to_dict() for entry in frozen],
        "unknown": sorted(unknown),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _config_from_payload(payload: Mapping[str, Any]) -> FrozenSourceMapConfig:
    mappings = payload.get("mappings")
    unknown_fields = payload.get("unknown_fields")
    if not isinstance(mappings, list):
        raise ValueError("source-map config mappings must be a list")
    if not isinstance(unknown_fields, list):
        raise ValueError("source-map config unknown_fields must be a list")
    return FrozenSourceMapConfig(
        connector_id=_required_str(payload, "connector_id"),  # type: ignore[arg-type]
        schema_hash=_required_str(payload, "schema_hash"),
        proposal_hash=_required_str(payload, "proposal_hash"),
        config_hash=_required_str(payload, "config_hash"),
        mappings=tuple(_field_mapping_from_payload(item) for item in mappings),
        unknown_fields=tuple(str(item) for item in unknown_fields),
    )


def _proposal_from_payload(payload: Mapping[str, Any]) -> SourceMapProposal:
    entries = payload.get("entries")
    coverage = payload.get("coverage")
    actions = payload.get("required_operator_actions")
    if not isinstance(entries, list):
        raise ValueError("source-map proposal entries must be a list")
    if not isinstance(coverage, dict):
        raise ValueError("source-map proposal coverage must be an object")
    if not isinstance(actions, list):
        raise ValueError("source-map proposal required_operator_actions must be a list")
    return SourceMapProposal(
        connector_id=_required_str(payload, "connector_id"),  # type: ignore[arg-type]
        schema_hash=_required_str(payload, "schema_hash"),
        proposal_hash=_required_str(payload, "proposal_hash"),
        entries=tuple(_field_mapping_from_payload(item) for item in entries),
        coverage={str(key): int(value) for key, value in coverage.items()},
        required_operator_actions=tuple(str(item) for item in actions),
    )


def _field_mapping_from_payload(payload: object) -> ProposedFieldMapping:
    if not isinstance(payload, dict):
        raise ValueError("source-map mapping entries must be JSON objects")
    candidates = payload.get("candidate_evidence", ())
    if not isinstance(candidates, list | tuple):
        raise ValueError("source-map candidate_evidence must be a list")
    return ProposedFieldMapping(
        connector_id=_required_str(payload, "connector_id"),  # type: ignore[arg-type]
        contract=_required_str(payload, "contract"),
        internal_field=_required_str(payload, "internal_field"),
        source_object=_optional_str(payload, "source_object"),
        source_field=_optional_str(payload, "source_field"),
        source_path=_optional_str(payload, "source_path"),
        state=_required_str(payload, "state"),  # type: ignore[arg-type]
        semantic_role=_required_str(payload, "semantic_role"),
        value_direction=_value_direction_from_payload(payload),
        requires_human_confirmation=bool(payload.get("requires_human_confirmation")),
        confidence=float(payload.get("confidence", 0.0)),
        reason=_required_str(payload, "reason"),
        pii=_required_str(payload, "pii"),  # type: ignore[arg-type]
        llm_allowed=bool(payload.get("llm_allowed")),
        candidate_evidence=tuple(_candidate_from_payload(item) for item in candidates),
        transform=str(payload.get("transform", "none")),
    )


def _confirmation_from_payload(payload: object) -> MappingConfirmation:
    if not isinstance(payload, dict):
        raise ValueError("mapping confirmations must be JSON objects")
    verdict = _mapping_verdict_from_payload(payload)
    source_object = _optional_str(payload, "source_object")
    source_field = _optional_str(payload, "source_field")
    source_path = _optional_str(payload, "source_path")
    semantic_role = _optional_str(payload, "semantic_role")
    if verdict == "mapped":
        source_object = source_object or _required_str(payload, "source_object")
        source_field = source_field or _required_str(payload, "source_field")
        source_path = source_path or _required_str(payload, "source_path")
        semantic_role = semantic_role or _required_str(payload, "semantic_role")
    return MappingConfirmation(
        contract=_required_str(payload, "contract"),
        internal_field=_required_str(payload, "internal_field"),
        source_object=source_object,
        source_field=source_field,
        source_path=source_path,
        semantic_role=semantic_role,
        value_direction=_value_direction_from_payload(payload, default="not_applicable"),
        verdict=verdict,
        transform=_optional_str(payload, "transform"),
    )


def _candidate_from_payload(payload: object) -> MappingCandidateEvidence:
    if not isinstance(payload, dict):
        raise ValueError("source-map candidate evidence entries must be JSON objects")
    return MappingCandidateEvidence(
        source_object=_required_str(payload, "source_object"),
        source_field=_required_str(payload, "source_field"),
        source_path=_required_str(payload, "source_path"),
        rows_present=int(payload.get("rows_present", 0)),
        rows_nonempty=int(payload.get("rows_nonempty", 0)),
        rows_sampled=int(payload.get("rows_sampled", 0)),
        field_type=_required_str(payload, "field_type"),
        confidence=float(payload.get("confidence", 0.0)),
        reason=_required_str(payload, "reason"),
    )


def _candidate_from_field(
    source_object: str,
    source_field: str,
    source_path: str,
    confidence: float,
    reason: str,
) -> MappingCandidateEvidence:
    return MappingCandidateEvidence(
        source_object=source_object,
        source_field=source_field,
        source_path=source_path,
        rows_present=0,
        rows_nonempty=0,
        rows_sampled=0,
        field_type="unknown",
        confidence=confidence,
        reason=reason,
    )


def _mapping_verdict_from_payload(payload: Mapping[str, Any]) -> MappingVerdict:
    value = payload.get("verdict", "mapped")
    if value not in {"mapped", "not_mappable"}:
        raise ValueError("mapping confirmation verdict must be mapped or not_mappable")
    return value  # type: ignore[return-value]


def _value_direction_from_payload(
    payload: Mapping[str, Any],
    *,
    default: str | None = None,
) -> ValueDirection:
    value = payload.get("value_direction", default)
    if not isinstance(value, str) or value not in _VALUE_DIRECTIONS:
        raise ValueError("source-map value_direction must be a known value")
    return value  # type: ignore[return-value]


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"source-map config field {key} is required")
    return value


def _optional_str(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"source-map config field {key} must be a string")
    return value


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _snake(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return out or "custom_field"


_ATTIO_SOURCE_MAPS = {
    "CRMAccount": SourceObjectMap(
        vendor="Attio",
        object_name="companies",
        docs_url=(
            "https://docs.attio.com/rest-api/endpoint-reference/"
            "companies/list-company-records"
        ),
        fields={
            "account_id": SourceField("id", True, llm_allowed=False),
            "name": SourceField("name", True),
            "owner_id": SourceField("owner", False),
            "industry": SourceField("industry", False),
        },
    ),
    "CRMContact": SourceObjectMap(
        vendor="Attio",
        object_name="people",
        docs_url="https://docs.attio.com/rest-api/endpoint-reference/people/list-person-records",
        fields={
            "contact_id": SourceField("id", True, llm_allowed=False),
            "account_id": SourceField("associated_company", False, llm_allowed=False),
            "email": SourceField("email_addresses", True, pii="contact", llm_allowed=False),
            "name": SourceField("name", True, pii="contact"),
            "role": SourceField("role", False),
            "title": SourceField("job_title", False),
            "consent_to_contact": SourceField("consent_to_contact", False),
        },
    ),
}

_ROCKETLANE_SOURCE_MAPS = {
    "TimeToValueMilestone": SourceObjectMap(
        vendor="Rocketlane",
        object_name="Task",
        docs_url="https://developer.rocketlane.com/reference/get-all-tasks",
        fields={
            "account_id": SourceField("projectId", True, llm_allowed=False),
            "milestone": SourceField("taskName", True),
            "expected_by": SourceField("dueDate", True),
            "achieved_at": SourceField("completedAt", True),
            "evidence_signal_ids": SourceField("taskId", True, llm_allowed=False),
        },
    ),
}

_TELEMETRY_SOURCE_MAPS = {
    "Entitlement": SourceObjectMap(
        vendor="OpenTelemetry",
        object_name="OTelRequiredAttributes",
        docs_url="https://opentelemetry.io/docs/specs/otel/common/",
        fields={
            "account_id": SourceField("ultra_csm.account.id", True, llm_allowed=False),
            "capability": SourceField("ultra_csm.capability", True),
            "entitled_quantity": SourceField("ultra_csm.entitlement.quantity", False),
            "unit": SourceField("unit", False),
            "starts_at": SourceField("starts_at", False),
            "ends_at": SourceField("ends_at", False),
        },
    ),
    "UsageSignal": SourceObjectMap(
        vendor="OpenTelemetry",
        object_name="OTelRequiredAttributes",
        docs_url="https://opentelemetry.io/docs/specs/otel/metrics/data-model/",
        fields={
            "signal_id": SourceField("ultra_csm.signal.id", False, llm_allowed=False),
            "account_id": SourceField("ultra_csm.account.id", True, llm_allowed=False),
            "grain": SourceField("ultra_csm.grain", True),
            "subject_id": SourceField(
                "ultra_csm.subject.id",
                False,
                pii="contact",
                llm_allowed=False,
            ),
            "metric_name": SourceField("ultra_csm.metric.name", True),
            "value": SourceField("value", False),
            "unit": SourceField("unit", False),
            "observed_at": SourceField("time_unix_nano", False),
            "source_ref": SourceField("ultra_csm.source.ref", True),
        },
    ),
}
