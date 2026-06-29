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
from typing import Literal, Mapping

from ultra_csm.data_plane.connector_catalog import CONNECTOR_SPECS
from ultra_csm.data_plane.explorer import DiscoveredField, DiscoveredObject, SchemaSnapshot
from ultra_csm.data_plane.readiness import ConnectorId
from ultra_csm.data_plane.source_maps import ALL_SOURCE_MAPS, SourceField, SourceObjectMap


MappingState = Literal["mapped", "ambiguous_confirm", "missing_to_unknown"]
ValueDirection = Literal[
    "not_applicable",
    "higher_is_better",
    "lower_is_better",
    "ordered_confirm",
    "direction_confirm",
]


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

    @property
    def key(self) -> str:
        return f"{self.contract}.{self.internal_field}"

    def to_dict(self) -> dict:
        return asdict(self)


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
    source_object: str
    source_field: str
    source_path: str
    semantic_role: str
    value_direction: ValueDirection = "not_applicable"


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
        frozen.append(_confirmed(entry, confirmation))

    config_hash = _config_hash(proposal, frozen, unknown)
    return FrozenSourceMapConfig(
        connector_id=proposal.connector_id,
        schema_hash=proposal.schema_hash,
        proposal_hash=proposal.proposal_hash,
        config_hash=config_hash,
        mappings=tuple(frozen),
        unknown_fields=tuple(sorted(unknown)),
    )


def _propose_field(
    connector_id: ConnectorId,
    contract: str,
    internal_field: str,
    source_field: SourceField,
    source_object: DiscoveredObject | None,
) -> ProposedFieldMapping:
    semantic_role = _semantic_role(contract, internal_field)
    direction = _value_direction(contract, internal_field)
    needs_direction_confirm = direction in {"ordered_confirm", "direction_confirm"}
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
            confidence=0.72 if not discovered_field.custom else 0.58,
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
    )


def _confirmed(
    entry: ProposedFieldMapping,
    confirmation: MappingConfirmation,
) -> ProposedFieldMapping:
    return ProposedFieldMapping(
        connector_id=entry.connector_id,
        contract=entry.contract,
        internal_field=entry.internal_field,
        source_object=confirmation.source_object,
        source_field=confirmation.source_field,
        source_path=confirmation.source_path,
        state="mapped",
        semantic_role=confirmation.semantic_role,
        value_direction=confirmation.value_direction,
        requires_human_confirmation=False,
        confidence=1.0,
        reason="human-confirmed mapping frozen into deterministic config",
        pii=entry.pii,
        llm_allowed=entry.llm_allowed,
    )


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


def _config_hash(
    proposal: SourceMapProposal,
    frozen: list[ProposedFieldMapping],
    unknown: list[str],
) -> str:
    payload = {
        "proposal_hash": proposal.proposal_hash,
        "mappings": [entry.to_dict() for entry in frozen],
        "unknown": sorted(unknown),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


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
