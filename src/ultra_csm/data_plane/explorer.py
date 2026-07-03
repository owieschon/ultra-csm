"""Schema explorers for live connector onboarding."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import TYPE_CHECKING, Any, Callable, Mapping

from ultra_csm.data_plane.connector_catalog import CONNECTOR_SPECS
from ultra_csm.data_plane.live_smoke import (
    HttpClient,
    HttpRequest,
    UrllibHttpClient,
    _env,
    _json_headers,
    _missing_env,
)
from ultra_csm.data_plane.readiness import ConnectorId, SourceReadiness

if TYPE_CHECKING:
    from ultra_csm.data_plane.source_mapping import SourceMapProposal


@dataclass(frozen=True)
class DiscoveredField:
    name: str
    field_type: str
    required: bool
    custom: bool
    source_path: str
    rows_present: int = 0
    rows_nonempty: int = 0
    rows_sampled: int = 0
    # Deterministic value-shape class ("id_like", "name_like",
    # "low_cardinality_enum", ...) computed from sampled values when the
    # connector has them (external_book relay). "" when unknown (schema-only
    # connectors like Salesforce describe).
    value_shape: str = ""
    distinct_count: int = 0
    # Source-declared relationship metadata, when the source's own schema API
    # provides it (e.g. Salesforce describe: a Lookup(Account) field carries
    # references=("Account",)). This is ground truth from the source -- a
    # foreign key that is KNOWN, not inferred from value shapes. Empty when the
    # source has no schema (raw JSON / CSV relay), where shape heuristics apply.
    references: tuple[str, ...] = ()
    relationship_name: str = ""


@dataclass(frozen=True)
class DiscoveredObject:
    name: str
    label: str
    fields: tuple[DiscoveredField, ...]


@dataclass(frozen=True)
class SchemaSnapshot:
    connector_id: ConnectorId
    schema_hash: str
    objects: tuple[DiscoveredObject, ...]
    sample_counts: dict[str, int]
    source_steps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExplorerResult:
    connector_id: ConnectorId
    ok: bool
    readiness: SourceReadiness
    missing_env: tuple[str, ...]
    steps: tuple[str, ...]
    snapshot: SchemaSnapshot | None = None
    mapping_proposal: SourceMapProposal | None = None
    errors: tuple[str, ...] = ()
    dry_run_requests: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExploreStep:
    name: str
    request: HttpRequest
    expected_statuses: tuple[int, ...] = (200,)


Parser = Callable[[dict[str, object]], tuple[tuple[DiscoveredObject, ...], int]]


def run_explorer(
    connector_id: ConnectorId,
    *,
    env: Mapping[str, str],
    client: HttpClient | None = None,
    dry_run: bool = False,
) -> ExplorerResult:
    spec = CONNECTOR_SPECS[connector_id]
    missing = _missing_env(connector_id, env)
    if missing:
        return ExplorerResult(
            connector_id=connector_id,
            ok=False,
            readiness=SourceReadiness(
                connector_id=connector_id,
                mode="live",
                state="shape_verified_pending_live_creds",
                connected=False,
                rails_degraded=spec.source_contracts,
                required_operator_actions=tuple(f"set {key}" for key in missing),
            ),
            missing_env=missing,
            steps=(),
        )

    try:
        steps = EXPLORER_BUILDERS[connector_id](env)
    except KeyError as exc:
        missing_key = str(exc).strip("'")
        return ExplorerResult(
            connector_id=connector_id,
            ok=False,
            readiness=SourceReadiness(
                connector_id=connector_id,
                mode="live",
                state="shape_verified_pending_live_creds",
                connected=False,
                rails_degraded=spec.source_contracts,
                required_operator_actions=(f"set {missing_key}",),
            ),
            missing_env=(missing_key,),
            steps=(),
        )

    if dry_run:
        return ExplorerResult(
            connector_id=connector_id,
            ok=True,
            readiness=SourceReadiness(
                connector_id=connector_id,
                mode="live",
                state="shape_verified_pending_live_creds",
                connected=False,
                rails_degraded=(),
                required_operator_actions=("run without --dry-run to discover live schema",),
                evidence=tuple(name for name, _, _ in steps),
            ),
            missing_env=(),
            steps=tuple(name for name, _, _ in steps),
            dry_run_requests=tuple(step.request.url for _, step, _ in steps),
        )

    http = client or UrllibHttpClient()
    completed: list[str] = []
    errors: list[str] = []
    objects: list[DiscoveredObject] = []
    sample_counts: dict[str, int] = {}
    bearer_token: str | None = None
    raw_fingerprints: list[object] = []

    for name, step, parser in steps:
        req = step.request
        if bearer_token is not None and req.headers.get("authorization") == "Bearer ${access_token}":
            req = HttpRequest(
                method=req.method,
                url=req.url,
                headers={**req.headers, "authorization": f"Bearer {bearer_token}"},
                body=req.body,
            )
        try:
            response = http.send(req)
        except Exception as exc:  # pragma: no cover - live network boundary.
            errors.append(f"{name}: {exc}")
            break
        if response.status not in step.expected_statuses:
            errors.append(f"{name}: unexpected status {response.status}")
            break
        try:
            raw = response.json()
        except (ValueError, TypeError):
            raw = {}
        if name == "oauth_refresh":
            if not isinstance(raw, dict) or not isinstance(raw.get("access_token"), str):
                errors.append(f"{name}: missing access_token")
                break
            bearer_token = raw["access_token"]
            completed.append(name)
            raw_fingerprints.append({"step": name, "status": response.status})
            continue
        if not isinstance(raw, dict):
            errors.append(f"{name}: expected JSON object")
            break
        try:
            discovered, sample_count = parser(raw)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            break
        objects.extend(discovered)
        sample_counts[name] = sample_count
        completed.append(name)
        raw_fingerprints.append(_fingerprintable(name, raw))

    ok = not errors
    snapshot = None
    mapping_proposal = None
    if ok:
        from ultra_csm.data_plane.source_mapping import propose_source_mapping

        snapshot = SchemaSnapshot(
            connector_id=connector_id,
            schema_hash=_schema_hash(connector_id, raw_fingerprints),
            objects=tuple(objects),
            sample_counts=sample_counts,
            source_steps=tuple(completed),
        )
        mapping_proposal = propose_source_mapping(snapshot)
    return ExplorerResult(
        connector_id=connector_id,
        ok=ok,
        readiness=SourceReadiness(
            connector_id=connector_id,
            mode="live",
            state="live_schema_verified" if ok else "degraded",
            connected=ok,
            rails_degraded=() if ok else spec.source_contracts,
            required_operator_actions=() if ok else ("review connector schema access",),
            evidence=tuple(completed),
        ),
        missing_env=(),
        steps=tuple(completed),
        snapshot=snapshot,
        mapping_proposal=mapping_proposal,
        errors=tuple(errors),
    )


def _attio_explorer_steps(env: Mapping[str, str]):
    token = _env(env, "ULTRA_CSM_ATTIO_ACCESS_TOKEN")
    base = env.get("ULTRA_CSM_ATTIO_BASE_URL", "https://api.attio.com").rstrip("/")
    headers = _json_headers({"authorization": f"Bearer {token}"})
    json_headers = _json_headers({"authorization": f"Bearer {token}", "content-type": "application/json"})
    return (
        ("self", ExploreStep("self", HttpRequest("GET", f"{base}/v2/self", headers)), _parse_empty),
        ("objects", ExploreStep("objects", HttpRequest("GET", f"{base}/v2/objects", headers)), _parse_attio_objects),
        (
            "companies_attributes",
            ExploreStep(
                "companies_attributes",
                HttpRequest("GET", f"{base}/v2/objects/companies/attributes", headers),
            ),
            lambda raw: _parse_attio_attributes(raw, "companies"),
        ),
        (
            "people_attributes",
            ExploreStep(
                "people_attributes",
                HttpRequest("GET", f"{base}/v2/objects/people/attributes", headers),
            ),
            lambda raw: _parse_attio_attributes(raw, "people"),
        ),
        (
            "companies_sample",
            ExploreStep(
                "companies_sample",
                HttpRequest(
                    "POST",
                    f"{base}/v2/objects/companies/records/query",
                    json_headers,
                    body=b'{"limit":1,"offset":0}',
                ),
            ),
            lambda raw: ((), _count_data(raw)),
        ),
        (
            "people_sample",
            ExploreStep(
                "people_sample",
                HttpRequest(
                    "POST",
                    f"{base}/v2/objects/people/records/query",
                    json_headers,
                    body=b'{"limit":1,"offset":0}',
                ),
            ),
            lambda raw: ((), _count_data(raw)),
        ),
    )


def _salesforce_explorer_steps(env: Mapping[str, str]):
    from ultra_csm.data_plane.live_smoke import _salesforce_steps

    smoke_steps = _salesforce_steps(env)
    instance = _env(env, "ULTRA_CSM_SALESFORCE_INSTANCE_URL").rstrip("/")
    api_version = env.get("ULTRA_CSM_SALESFORCE_API_VERSION", "v61.0")
    direct_token = env.get("ULTRA_CSM_SALESFORCE_ACCESS_TOKEN")
    headers = _json_headers({
        "authorization": (
            f"Bearer {direct_token}" if direct_token else "Bearer ${access_token}"
        )
    })
    object_names = ("Contact", "Case", "Opportunity", "Task", "Event")
    prefix = () if direct_token else (("oauth_refresh", smoke_steps[0], _parse_empty),)
    describe_global = smoke_steps[0 if direct_token else 1]
    account_describe = smoke_steps[1 if direct_token else 2]
    return (
        *prefix,
        ("describe_global", describe_global, _parse_salesforce_global),
        ("account_describe", account_describe, _parse_salesforce_describe),
        *tuple(
            (
                f"{object_name.lower()}_describe",
                ExploreStep(
                    f"{object_name.lower()}_describe",
                    HttpRequest(
                        "GET",
                        f"{instance}/services/data/{api_version}/sobjects/{object_name}/describe",
                        headers,
                    ),
                ),
                _parse_salesforce_describe,
            )
            for object_name in object_names
        ),
    )


def _gainsight_explorer_steps(env: Mapping[str, str]):
    domain = _env(env, "ULTRA_CSM_GAINSIGHT_DOMAIN").rstrip("/")
    token = _env(env, "ULTRA_CSM_GAINSIGHT_TOKEN")
    headers = _json_headers({"accesskey": token})
    objects = tuple(
        raw.strip()
        for raw in env.get(
            "ULTRA_CSM_GAINSIGHT_DISCOVERY_OBJECTS",
            "Company,CTA,SuccessPlan,Scorecard Fact,Unified Scorecard Fact-Company,Scorecard Measures",
        ).split(",")
        if raw.strip()
    )
    return tuple(
        (
            f"{object_name.lower().replace(' ', '_')}_metadata",
            ExploreStep(
                f"{object_name}_metadata",
                HttpRequest(
                    "GET",
                    f"{domain}/v1/meta/services/objects/{parse_quote(object_name)}/describe?ic=true&cl=3&idd=true",
                    headers,
                ),
            ),
            lambda raw, object_name=object_name: _parse_gainsight_describe(raw, object_name),
        )
        for object_name in objects
    )


def _rocketlane_explorer_steps(env: Mapping[str, str]):
    token = _env(env, "ULTRA_CSM_ROCKETLANE_API_KEY")
    base = env.get("ULTRA_CSM_ROCKETLANE_BASE_URL", "https://api.rocketlane.com/api/1.0").rstrip("/")
    headers = _json_headers({"api-key": token})
    return (
        (
            "fields",
            ExploreStep("fields", HttpRequest("GET", f"{base}/fields?pageSize=100", headers)),
            _parse_rocketlane_fields,
        ),
        (
            "projects_sample",
            ExploreStep(
                "projects_sample",
                HttpRequest("GET", f"{base}/projects?pageSize=1&includeAllFields=true", headers),
            ),
            lambda raw: _parse_rocketlane_sample(raw, "Project"),
        ),
        (
            "phases_sample",
            ExploreStep("phases_sample", HttpRequest("GET", f"{base}/phases?pageSize=1", headers)),
            lambda raw: _parse_rocketlane_sample(raw, "Phase"),
        ),
        (
            "tasks_sample",
            ExploreStep("tasks_sample", HttpRequest("GET", f"{base}/tasks?pageSize=1", headers)),
            lambda raw: _parse_rocketlane_sample(raw, "Task"),
        ),
    )


def _telemetry_explorer_steps(env: Mapping[str, str]):
    endpoint = _env(env, "OTEL_EXPORTER_OTLP_ENDPOINT").rstrip("/")
    steps = [
        (
            "otlp_endpoint_reachable",
            ExploreStep(
                "otlp_endpoint_reachable",
                HttpRequest("GET", endpoint, _json_headers(), None),
                expected_statuses=(200, 404, 405),
            ),
            _parse_telemetry_required_attributes,
        )
    ]
    if env.get("ULTRA_CSM_TELEMETRY_CATALOG_URL"):
        steps.append(
            (
                "telemetry_catalog",
                ExploreStep(
                    "telemetry_catalog",
                    HttpRequest(
                        "GET",
                        env["ULTRA_CSM_TELEMETRY_CATALOG_URL"],
                        _json_headers(),
                    ),
                    expected_statuses=(200,),
                ),
                _parse_telemetry_catalog,
            )
        )
    return tuple(steps)


EXPLORER_BUILDERS = {
    "attio_crm": _attio_explorer_steps,
    "salesforce_crm": _salesforce_explorer_steps,
    "gainsight_cs": _gainsight_explorer_steps,
    "rocketlane_onboarding": _rocketlane_explorer_steps,
    "product_telemetry": _telemetry_explorer_steps,
}


def parse_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _parse_empty(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    return (), 0


def _parse_attio_objects(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = _list(raw.get("data"))
    objects = tuple(
        DiscoveredObject(
            name=str(item.get("api_slug") or item.get("slug") or item.get("id") or ""),
            label=str(item.get("singular_noun") or item.get("title") or item.get("api_slug") or ""),
            fields=(),
        )
        for item in data
        if isinstance(item, dict)
    )
    return tuple(obj for obj in objects if obj.name), len(data)


def _parse_attio_attributes(raw: dict[str, object], object_name: str) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = _list(raw.get("data"))
    fields = tuple(
        DiscoveredField(
            name=str(item.get("api_slug") or item.get("slug") or item.get("id") or ""),
            field_type=str(item.get("type") or item.get("attribute_type") or "unknown"),
            required=bool(item.get("is_required", False)),
            custom=not bool(item.get("is_system_attribute", False)),
            source_path=f"values.{item.get('api_slug') or item.get('slug') or item.get('id')}",
        )
        for item in data
        if isinstance(item, dict)
    )
    return (DiscoveredObject(object_name, object_name.title(), tuple(field for field in fields if field.name)),), len(data)


def _parse_salesforce_global(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = _list(raw.get("sobjects"))
    objects = tuple(
        DiscoveredObject(
            name=str(item.get("name") or ""),
            label=str(item.get("label") or item.get("name") or ""),
            fields=(),
        )
        for item in data
        if isinstance(item, dict)
    )
    return tuple(obj for obj in objects if obj.name), len(data)


def _parse_salesforce_describe(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    object_name = str(raw.get("name") or "")
    fields = tuple(
        DiscoveredField(
            name=str(item.get("name") or ""),
            field_type=str(item.get("type") or "unknown"),
            required=not bool(item.get("nillable", True)),
            custom=bool(item.get("custom", False)),
            source_path=str(item.get("name") or ""),
            # Capture the foreign-key graph the source declares: a reference
            # field's referenceTo names the object(s) it points at. Previously
            # discarded, which forced downstream code to re-infer joins from
            # value shapes instead of reading them from the source.
            references=tuple(
                str(ref) for ref in _list(item.get("referenceTo")) if ref
            ),
            relationship_name=str(item.get("relationshipName") or ""),
        )
        for item in _list(raw.get("fields"))
        if isinstance(item, dict)
    )
    if not object_name:
        raise ValueError("missing Salesforce object name")
    return (
        DiscoveredObject(
            name=object_name,
            label=str(raw.get("label") or object_name),
            fields=tuple(field for field in fields if field.name),
        ),
    ), len(fields)


def _parse_gainsight_describe(raw: dict[str, object], fallback_name: str) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = raw.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        obj = data[0]
    elif isinstance(data, dict):
        obj = data
    else:
        obj = raw
    object_name = str(obj.get("objectName") or obj.get("name") or fallback_name)
    raw_fields = obj.get("fields") or obj.get("fieldMetaData") or obj.get("field_metadata") or []
    fields = tuple(
        DiscoveredField(
            name=str(item.get("fieldName") or item.get("name") or item.get("field_name") or ""),
            field_type=str(item.get("dataType") or item.get("type") or item.get("datatype") or "unknown"),
            required=bool(item.get("required", False)),
            custom=bool(item.get("custom", False) or item.get("isCustom", False)),
            source_path=str(item.get("fieldName") or item.get("name") or item.get("field_name") or ""),
        )
        for item in _list(raw_fields)
        if isinstance(item, dict)
    )
    return (
        DiscoveredObject(
            name=object_name,
            label=str(obj.get("label") or obj.get("displayName") or object_name),
            fields=tuple(field for field in fields if field.name),
        ),
    ), len(fields)


def _parse_rocketlane_fields(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = _list(raw.get("data"))
    by_object: dict[str, list[DiscoveredField]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        object_type = str(item.get("objectType") or item.get("object") or "UNKNOWN")
        field_name = str(item.get("fieldName") or item.get("fieldLabel") or item.get("name") or "")
        if not field_name:
            continue
        by_object.setdefault(object_type, []).append(
            DiscoveredField(
                name=field_name,
                field_type=str(item.get("fieldType") or item.get("type") or "unknown"),
                required=bool(item.get("required", False)),
                custom=True,
                source_path=f"fields.{field_name}",
            )
        )
    objects = tuple(
        DiscoveredObject(name=object_type, label=object_type.title(), fields=tuple(fields))
        for object_type, fields in sorted(by_object.items())
    )
    return objects, len(data)


def _parse_rocketlane_sample(raw: dict[str, object], object_name: str) -> tuple[tuple[DiscoveredObject, ...], int]:
    data = _list(raw.get("data"))
    first = data[0] if data and isinstance(data[0], dict) else {}
    fields = tuple(
        DiscoveredField(
            name=str(key),
            field_type=type(value).__name__,
            required=False,
            custom=False,
            source_path=str(key),
        )
        for key, value in sorted(first.items())
    )
    return (DiscoveredObject(object_name, object_name, fields),), len(data)


def _parse_telemetry_catalog(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    metrics = _list(raw.get("metrics"))
    fields = tuple(
        DiscoveredField(
            name=str(item.get("name") or ""),
            field_type=str(item.get("unit") or item.get("type") or "metric"),
            required=True,
            custom=False,
            source_path=f"metrics.{item.get('name')}",
        )
        for item in metrics
        if isinstance(item, dict)
    )
    return (DiscoveredObject("OTelMetricCatalog", "OTel Metric Catalog", tuple(field for field in fields if field.name)),), len(metrics)


def _parse_telemetry_required_attributes(raw: dict[str, object]) -> tuple[tuple[DiscoveredObject, ...], int]:
    fields = tuple(
        DiscoveredField(
            name=name,
            field_type="attribute",
            required=True,
            custom=name.startswith("ultra_csm."),
            source_path=f"resource_or_datapoint.attributes.{name}",
        )
        for name in (
            "service.name",
            "ultra_csm.tenant.id",
            "ultra_csm.account.id",
            "ultra_csm.capability",
            "ultra_csm.metric.name",
            "ultra_csm.grain",
            "ultra_csm.source.ref",
        )
    )
    return (DiscoveredObject("OTelRequiredAttributes", "OTel Required Attributes", fields),), 0


def _count_data(raw: dict[str, object]) -> int:
    return len(_list(raw.get("data") or raw.get("records")))


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _fingerprintable(name: str, raw: dict[str, object]) -> object:
    return {"step": name, "payload": raw}


def _schema_hash(connector_id: ConnectorId, payloads: list[object]) -> str:
    raw = json.dumps({"connector_id": connector_id, "payloads": payloads}, sort_keys=True)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
