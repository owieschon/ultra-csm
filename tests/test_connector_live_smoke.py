"""Credential-boundary live connector smoke checks."""

from __future__ import annotations

from io import BytesIO
import json
from urllib.error import HTTPError

from ultra_csm.data_plane.live_smoke import (
    HttpRequest,
    HttpResponse,
    UrllibHttpClient,
    run_smoke,
)


class RecordingClient:
    def __init__(self, status: int = 200):
        self.status = status
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        return HttpResponse(status=self.status, body=b"{}", headers={})


class SalesforceRecordingClient(RecordingClient):
    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if req.url.endswith("/services/oauth2/token"):
            return HttpResponse(
                status=200,
                body=b'{"access_token":"access-token"}',
                headers={},
            )
        return HttpResponse(status=200, body=b"{}", headers={})


def test_every_live_smoke_reports_missing_credentials_without_network():
    for connector_id in (
        "salesforce_crm",
        "attio_crm",
        "gainsight_cs",
        "rocketlane_onboarding",
        "product_telemetry",
    ):
        client = RecordingClient()

        result = run_smoke(connector_id, env={}, client=client)

        assert result.ok is False
        assert result.readiness.state == "shape_verified_pending_live_creds"
        assert result.missing_env
        assert client.requests == []


def test_attio_smoke_builds_read_only_discovery_requests():
    client = RecordingClient()

    result = run_smoke(
        "attio_crm",
        env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "token"},
        client=client,
    )

    assert result.ok is True
    assert result.readiness.state == "live_smoke_verified"
    assert [req.method for req in client.requests] == ["GET", "GET", "POST", "POST"]
    assert [req.url for req in client.requests] == [
        "https://api.attio.com/v2/self",
        "https://api.attio.com/v2/objects",
        "https://api.attio.com/v2/objects/companies/records/query",
        "https://api.attio.com/v2/objects/people/records/query",
    ]
    assert all(req.headers["authorization"] == "Bearer token" for req in client.requests)
    assert json.loads(client.requests[2].body.decode("utf-8")) == {"limit": 1, "offset": 0}


def test_salesforce_smoke_builds_oauth_describe_requests():
    client = SalesforceRecordingClient()

    result = run_smoke(
        "salesforce_crm",
        env={
            "ULTRA_CSM_SALESFORCE_INSTANCE_URL": "https://example.my.salesforce.com",
            "ULTRA_CSM_SALESFORCE_CLIENT_ID": "client",
            "ULTRA_CSM_SALESFORCE_CLIENT_SECRET": "secret",
            "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN": "refresh",
            "ULTRA_CSM_SALESFORCE_API_VERSION": "v61.0",
        },
        client=client,
    )

    assert result.ok is True
    assert [req.method for req in client.requests] == ["POST", "GET", "GET"]
    assert client.requests[0].url == "https://login.salesforce.com/services/oauth2/token"
    assert client.requests[1].url == "https://example.my.salesforce.com/services/data/v61.0/sobjects/"
    assert client.requests[2].url == (
        "https://example.my.salesforce.com/services/data/v61.0/sobjects/Account/describe"
    )
    assert b"grant_type=refresh_token" in client.requests[0].body
    assert client.requests[1].headers["authorization"] == "Bearer access-token"
    assert client.requests[2].headers["authorization"] == "Bearer access-token"


def test_salesforce_smoke_fails_when_oauth_response_has_no_token():
    client = RecordingClient()

    result = run_smoke(
        "salesforce_crm",
        env={
            "ULTRA_CSM_SALESFORCE_INSTANCE_URL": "https://example.my.salesforce.com",
            "ULTRA_CSM_SALESFORCE_CLIENT_ID": "client",
            "ULTRA_CSM_SALESFORCE_CLIENT_SECRET": "secret",
            "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN": "refresh",
        },
        client=client,
    )

    assert result.ok is False
    assert result.readiness.state == "degraded"
    assert result.errors == ("oauth_refresh: missing access_token",)


def test_gainsight_smoke_builds_metadata_request():
    client = RecordingClient()

    result = run_smoke(
        "gainsight_cs",
        env={
            "ULTRA_CSM_GAINSIGHT_DOMAIN": "https://tenant.gainsightcloud.com",
            "ULTRA_CSM_GAINSIGHT_TOKEN": "token",
        },
        client=client,
    )

    assert result.ok is True
    assert len(client.requests) == 1
    assert client.requests[0].url == (
        "https://tenant.gainsightcloud.com/v1/meta/services/objects/Company/"
        "describe?ic=true&cl=3&idd=true"
    )
    assert client.requests[0].headers["accesskey"] == "token"


def test_rocketlane_smoke_builds_project_sample_request():
    client = RecordingClient()

    result = run_smoke(
        "rocketlane_onboarding",
        env={"ULTRA_CSM_ROCKETLANE_API_KEY": "token"},
        client=client,
    )

    assert result.ok is True
    assert len(client.requests) == 1
    assert client.requests[0].url == (
        "https://api.rocketlane.com/api/1.0/projects?pageSize=1&includeAllFields=true"
    )
    assert client.requests[0].headers["api-key"] == "token"


def test_telemetry_smoke_accepts_common_collector_liveness_statuses():
    for status in (200, 404, 405):
        client = RecordingClient(status=status)

        result = run_smoke(
            "product_telemetry",
            env={"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
            client=client,
        )

        assert result.ok is True
        assert client.requests[0].url == "http://localhost:4318"


def test_live_smoke_degrades_on_unexpected_status():
    client = RecordingClient(status=500)

    result = run_smoke(
        "rocketlane_onboarding",
        env={"ULTRA_CSM_ROCKETLANE_API_KEY": "token"},
        client=client,
    )

    assert result.ok is False
    assert result.readiness.state == "degraded"
    assert result.errors == ("projects_sample: unexpected status 500",)


def test_urllib_client_returns_http_error_status(monkeypatch):
    def raise_404(*args, **kwargs):
        raise HTTPError(
            url="http://localhost:4318",
            code=404,
            msg="not found",
            hdrs={},
            fp=BytesIO(b"missing"),
        )

    monkeypatch.setattr("ultra_csm.data_plane.live_smoke.request.urlopen", raise_404)

    response = UrllibHttpClient().send(
        HttpRequest("GET", "http://localhost:4318", headers={})
    )

    assert response.status == 404
    assert response.body == b"missing"
