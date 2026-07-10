"""Verify a deployed sandbox without printing request or response bodies."""

from __future__ import annotations

import argparse
import uuid
from urllib.parse import urlsplit

import httpx

EXPECTED_OPENAPI_PATHS = {
    "/health",
    "/demo/action-control/sandbox/evaluate",
}


def _https_origin(value: str, label: str) -> str:
    normalized = value.removesuffix("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be one exact HTTPS origin")
    return normalized


def _command(run_id: str, index: int, command_type: str, **extra) -> dict:
    return {
        "command_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{index}:{command_type}")),
        "type": command_type,
        **extra,
    }


def verify(base_url: str, ui_origin: str) -> None:
    base = _https_origin(base_url, "base URL")
    origin = _https_origin(ui_origin, "UI origin")
    headers = {"Origin": origin}
    with httpx.Client(base_url=base, timeout=15, follow_redirects=False) as client:
        health = client.get("/health", headers=headers)
        _assert_response(health, 200, origin)
        health_body = health.json()
        if health_body != {
            "status": "ok",
            "mode": "rollback_isolated_synthetic",
            "outbound_effects_enabled": False,
        }:
            raise RuntimeError("health contract mismatch")

        schema = client.get("/openapi.json", headers=headers)
        _assert_response(schema, 200, origin)
        if set(schema.json().get("paths", {})) != EXPECTED_OPENAPI_PATHS:
            raise RuntimeError("deployed OpenAPI contains an unexpected route")

        missing = client.get("/proposals", headers=headers)
        _assert_response(missing, 404, origin)

        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-hosted-action-control-smoke-v1"))
        commands: list[dict] = []
        current = _evaluate(client, origin, run_id, commands, None)
        for command_type, extra in (
            ("approve_exact", {}),
            ("commit_simulated", {}),
            ("retry_same_commit", {}),
            (
                "probe_tamper",
                {"draft": "Synthetic smoke probe changes approved bytes and must be refused."},
            ),
        ):
            commands.append(_command(run_id, len(commands), command_type, **extra))
            current = _evaluate(
                client,
                origin,
                run_id,
                commands,
                current["state_sha256"],
            )

        if current["state"] != "refused_payload_mismatch":
            raise RuntimeError("tamper-refusal terminal state was not reached")
        if current["idempotency_probe"]["outbox_rows"] != 1:
            raise RuntimeError("duplicate suppression proof is missing")
        if current["isolation"]["external_effect"] is not False:
            raise RuntimeError("sandbox claimed an external effect")

        sentinel = "PRIVATE-DEPLOY-SMOKE-SENTINEL"
        invalid = client.post(
            "/demo/action-control/sandbox/evaluate",
            headers=headers,
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": run_id,
                "expected_state_sha256": "0" * 64,
                "commands": [
                    _command(
                        run_id,
                        0,
                        "revise_and_approve",
                        draft=sentinel + "x" * 800,
                    )
                ],
            },
        )
        _assert_response(invalid, 422, origin)
        if sentinel in invalid.text:
            raise RuntimeError("validation response reflected private input")


def _evaluate(
    client: httpx.Client,
    origin: str,
    run_id: str,
    commands: list[dict],
    expected_state_sha256: str | None,
) -> dict:
    response = client.post(
        "/demo/action-control/sandbox/evaluate",
        headers={"Origin": origin},
        json={
            "schema_version": "action-control.sandbox-command-log.v1",
            "run_id": run_id,
            "expected_state_sha256": expected_state_sha256,
            "commands": commands,
        },
    )
    _assert_response(response, 200, origin)
    return response.json()


def _assert_response(response: httpx.Response, status: int, origin: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"unexpected HTTP status: {response.status_code} != {status}")
    if response.headers.get("cache-control") != "no-store":
        raise RuntimeError("response is missing Cache-Control: no-store")
    if response.headers.get("access-control-allow-origin") != origin:
        raise RuntimeError("response CORS origin does not exactly match the UI origin")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--ui-origin", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    verify(args.base_url, args.ui_origin)
    print("hosted Action Control verification passed: routes, CORS, no-store, journey, privacy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
