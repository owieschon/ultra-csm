"""Credential-boundary smoke checks for live data-plane connectors."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Protocol
from urllib import error, parse, request

from ultra_csm.data_plane.connector_catalog import CONNECTOR_SPECS
from ultra_csm.data_plane.readiness import ConnectorId, SourceReadiness


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))


class HttpClient(Protocol):
    def send(self, req: HttpRequest) -> HttpResponse: ...


class UrllibHttpClient:
    def send(self, req: HttpRequest) -> HttpResponse:
        # Block non-web schemes (e.g. file://) before issuing the request: urllib would
        # otherwise honor them, turning a misconfigured URL into a local file read.
        if parse.urlparse(req.url).scheme not in ("https", "http"):
            raise ValueError(f"refusing non-http(s) request URL: {req.url!r}")
        raw = request.Request(
            req.url,
            data=req.body,
            headers=dict(req.headers),
            method=req.method,
        )
        try:
            with request.urlopen(raw, timeout=15) as resp:  # noqa: S310 - scheme-guarded live smoke path.
                return HttpResponse(
                    status=resp.status,
                    body=resp.read(),
                    headers=dict(resp.headers.items()),
                )
        except error.HTTPError as exc:
            return HttpResponse(
                status=exc.code,
                body=exc.read(),
                headers=dict(exc.headers.items()),
            )


@dataclass(frozen=True)
class SmokeStep:
    name: str
    request: HttpRequest
    expected_statuses: tuple[int, ...] = (200,)


@dataclass(frozen=True)
class SmokeResult:
    connector_id: ConnectorId
    ok: bool
    readiness: SourceReadiness
    missing_env: tuple[str, ...]
    steps: tuple[str, ...]
    errors: tuple[str, ...] = ()


def _env(env: Mapping[str, str], key: str, default: str | None = None) -> str:
    value = env.get(key, default)
    if value is None or value == "":
        raise KeyError(key)
    return value


def _json_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = {"accept": "application/json"}
    if extra:
        headers.update(extra)
    return headers


def _attio_steps(env: Mapping[str, str]) -> tuple[SmokeStep, ...]:
    token = _env(env, "ULTRA_CSM_ATTIO_ACCESS_TOKEN")
    base = env.get("ULTRA_CSM_ATTIO_BASE_URL", "https://api.attio.com").rstrip("/")
    headers = _json_headers({"authorization": f"Bearer {token}"})
    return (
        SmokeStep("self", HttpRequest("GET", f"{base}/v2/self", headers)),
        SmokeStep("objects", HttpRequest("GET", f"{base}/v2/objects", headers)),
        SmokeStep(
            "companies_sample",
            HttpRequest(
                "POST",
                f"{base}/v2/objects/companies/records/query",
                _json_headers(
                    {
                        "authorization": f"Bearer {token}",
                        "content-type": "application/json",
                    }
                ),
                body=b'{"limit":1,"offset":0}',
            ),
        ),
        SmokeStep(
            "people_sample",
            HttpRequest(
                "POST",
                f"{base}/v2/objects/people/records/query",
                _json_headers(
                    {
                        "authorization": f"Bearer {token}",
                        "content-type": "application/json",
                    }
                ),
                body=b'{"limit":1,"offset":0}',
            ),
        ),
    )


def _salesforce_steps(env: Mapping[str, str]) -> tuple[SmokeStep, ...]:
    login_url = env.get("ULTRA_CSM_SALESFORCE_LOGIN_URL", "https://login.salesforce.com").rstrip("/")
    api_version = env.get("ULTRA_CSM_SALESFORCE_API_VERSION", "v61.0")
    instance = _env(env, "ULTRA_CSM_SALESFORCE_INSTANCE_URL").rstrip("/")
    direct_token = env.get("ULTRA_CSM_SALESFORCE_ACCESS_TOKEN")
    headers = _json_headers({
        "authorization": (
            f"Bearer {direct_token}" if direct_token else "Bearer ${access_token}"
        )
    })
    describe_steps = (
        SmokeStep(
            "describe_global",
            HttpRequest("GET", f"{instance}/services/data/{api_version}/sobjects/", headers),
        ),
        SmokeStep(
            "account_describe",
            HttpRequest(
                "GET",
                f"{instance}/services/data/{api_version}/sobjects/Account/describe",
                headers,
            ),
        ),
    )
    if direct_token:
        return describe_steps
    token_body = parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": _env(env, "ULTRA_CSM_SALESFORCE_CLIENT_ID"),
            "client_secret": _env(env, "ULTRA_CSM_SALESFORCE_CLIENT_SECRET"),
            "refresh_token": _env(env, "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN"),
        }
    ).encode("utf-8")
    return (
        SmokeStep(
            "oauth_refresh",
            HttpRequest(
                "POST",
                f"{login_url}/services/oauth2/token",
                {"content-type": "application/x-www-form-urlencoded"},
                body=token_body,
            ),
        ),
        *describe_steps,
    )


def _gainsight_steps(env: Mapping[str, str]) -> tuple[SmokeStep, ...]:
    domain = _env(env, "ULTRA_CSM_GAINSIGHT_DOMAIN").rstrip("/")
    token = _env(env, "ULTRA_CSM_GAINSIGHT_TOKEN")
    headers = _json_headers({"accesskey": token})
    return (
        SmokeStep(
            "company_metadata",
            HttpRequest(
                "GET",
                f"{domain}/v1/meta/services/objects/Company/describe?ic=true&cl=3&idd=true",
                headers,
            ),
        ),
    )


def _rocketlane_steps(env: Mapping[str, str]) -> tuple[SmokeStep, ...]:
    token = _env(env, "ULTRA_CSM_ROCKETLANE_API_KEY")
    base = env.get("ULTRA_CSM_ROCKETLANE_BASE_URL", "https://api.rocketlane.com/api/1.0").rstrip("/")
    return (
        SmokeStep(
            "projects_sample",
            HttpRequest(
                "GET",
                f"{base}/projects?pageSize=1&includeAllFields=true",
                _json_headers({"api-key": token}),
            ),
        ),
    )


def _telemetry_steps(env: Mapping[str, str]) -> tuple[SmokeStep, ...]:
    endpoint = _env(env, "OTEL_EXPORTER_OTLP_ENDPOINT").rstrip("/")
    return (
        SmokeStep(
            "otlp_endpoint_reachable",
            HttpRequest("GET", endpoint, _json_headers(), None),
            expected_statuses=(200, 404, 405),
        ),
    )


STEP_BUILDERS = {
    "attio_crm": _attio_steps,
    "salesforce_crm": _salesforce_steps,
    "gainsight_cs": _gainsight_steps,
    "rocketlane_onboarding": _rocketlane_steps,
    "product_telemetry": _telemetry_steps,
}


def _missing_env(connector_id: ConnectorId, env: Mapping[str, str]) -> tuple[str, ...]:
    if connector_id == "salesforce_crm":
        instance_missing = () if env.get("ULTRA_CSM_SALESFORCE_INSTANCE_URL") else (
            "ULTRA_CSM_SALESFORCE_INSTANCE_URL",
        )
        if env.get("ULTRA_CSM_SALESFORCE_ACCESS_TOKEN"):
            return instance_missing
        oauth_missing = tuple(
            key
            for key in (
                "ULTRA_CSM_SALESFORCE_CLIENT_ID",
                "ULTRA_CSM_SALESFORCE_CLIENT_SECRET",
                "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",
            )
            if not env.get(key)
        )
        return (*instance_missing, *oauth_missing)
    return tuple(key for key in CONNECTOR_SPECS[connector_id].credential_env if not env.get(key))


def run_smoke(
    connector_id: ConnectorId,
    *,
    env: Mapping[str, str],
    client: HttpClient | None = None,
    dry_run: bool = False,
) -> SmokeResult:
    spec = CONNECTOR_SPECS[connector_id]
    missing = _missing_env(connector_id, env)
    if missing:
        return SmokeResult(
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
        steps = STEP_BUILDERS[connector_id](env)
    except KeyError as exc:
        missing_key = str(exc).strip("'")
        return SmokeResult(
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
        return SmokeResult(
            connector_id=connector_id,
            ok=True,
            readiness=SourceReadiness(
                connector_id=connector_id,
                mode="live",
                state="shape_verified_pending_live_creds",
                connected=False,
                rails_degraded=(),
                required_operator_actions=("run without --dry-run to verify live auth",),
                evidence=tuple(step.name for step in steps),
            ),
            missing_env=(),
            steps=tuple(step.name for step in steps),
        )

    http = client or UrllibHttpClient()
    completed: list[str] = []
    errors: list[str] = []
    bearer_token: str | None = None
    for step in steps:
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
            errors.append(f"{step.name}: {exc}")
            break
        if response.status not in step.expected_statuses:
            errors.append(f"{step.name}: unexpected status {response.status}")
            break
        if step.name == "oauth_refresh":
            try:
                oauth = response.json()
            except (ValueError, TypeError):
                errors.append(f"{step.name}: invalid token response")
                break
            if not isinstance(oauth, dict) or not isinstance(oauth.get("access_token"), str):
                errors.append(f"{step.name}: missing access_token")
                break
            bearer_token = oauth["access_token"]
        completed.append(step.name)

    ok = not errors
    return SmokeResult(
        connector_id=connector_id,
        ok=ok,
        readiness=SourceReadiness(
            connector_id=connector_id,
            mode="live",
            state="live_smoke_verified" if ok else "degraded",
            connected=ok,
            rails_degraded=() if ok else spec.source_contracts,
            required_operator_actions=() if ok else ("review connector credentials or API access",),
            evidence=tuple(completed),
        ),
        missing_env=(),
        steps=tuple(completed),
        errors=tuple(errors),
    )
