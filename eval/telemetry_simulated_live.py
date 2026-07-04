"""Fake event-level telemetry transport + reader vertical (Universe v2,
WS-Data-Classes Phase 1).

Mirrors the repo's existing simulated-vertical pattern (see
``eval/attio_simulated_onboarding.py`` and
``eval/product_telemetry_simulated_onboarding.py``): a local, stdlib-only,
in-memory fake HTTP transport serves fixture data over the SAME
``HttpRequest``/``HttpResponse`` shapes ``live_smoke.py`` uses, and a thin
reader consumes it into the exact ``TelemetryEvent`` shape
``telemetry_events.py``'s in-process derivation already produces -- proving
the wire format and the in-process derivation agree, not inventing a
second telemetry contract.

This is deliberately NOT routed through ``run_explorer``/
``connector_catalog.py``: those model OTel resource-*attribute* discovery
(mapping which fields exist), a different concern from fetching raw
per-asset event rows for two named accounts. Building a second
``ConnectorId``/``ConnectorSpec`` registration for an event-level fetch
that never needs source-map discovery would be speculative generality this
phase doesn't need (see docs/PROGRAM_REPORT_12.md's IF/THEN section).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.telemetry_events import (
    TELEMETRY_ACCOUNTS,
    TelemetryEvent,
    telemetry_events_through_day,
)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "telemetry_simulated_live.json"
EVENTS_ENDPOINT = "https://ultra-csm-simulated-telemetry.internal/v1/events"

# Coarse weekly sampling grid keeps fixture/request volume bounded across a
# 365-day year while still covering every bible checkpoint day for both
# accounts (20/50/310 Pinehill, 20/170/280 Meridian all fall on multiples
# of 10, comfortably covered by a 7-day stride plus the checkpoints
# themselves explicitly included).
_CHECKPOINTS: dict[str, tuple[int, ...]] = {
    "pinehill-transport": (20, 50, 310),
    "meridian-fleet": (20, 170, 280),
}


def _sample_days(as_of_day: int, account_slug: str) -> tuple[int, ...]:
    grid = set(range(0, as_of_day + 1, 7))
    grid.update(d for d in _CHECKPOINTS[account_slug] if d <= as_of_day)
    grid.add(0)
    return tuple(sorted(grid))


class FakeTelemetryEventsClient:
    """In-memory transport for the event-level telemetry API. Requests are
    ``GET {EVENTS_ENDPOINT}?account={slug}&as_of_day={n}``; the fake serves
    the same deterministic derivation ``telemetry_events.py`` computes
    in-process, over the wire, as a JSON array."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if not req.url.startswith(EVENTS_ENDPOINT):
            return HttpResponse(status=404, body=b"{}", headers={"content-type": "application/json"})
        query = dict(
            part.split("=", 1) for part in req.url.split("?", 1)[1].split("&")
        )
        account_slug = query["account"]
        as_of_day = int(query["as_of_day"])
        if account_slug not in TELEMETRY_ACCOUNTS:
            return HttpResponse(status=404, body=b"{}", headers={"content-type": "application/json"})
        events = telemetry_events_through_day(
            account_slug, as_of_day, sample_days=_sample_days(as_of_day, account_slug)
        )
        payload = {"events": [_event_wire_shape(e) for e in events]}
        return HttpResponse(
            status=200,
            body=json.dumps(payload, sort_keys=True).encode("utf-8"),
            headers={"content-type": "application/json"},
        )


def _event_wire_shape(event: TelemetryEvent) -> dict[str, Any]:
    """The fake API's wire shape for one event row."""

    return {
        "event_id": event.event_id,
        "account_id": event.account_id,
        "asset_id": event.asset_id,
        "event_type": event.event_type,
        "module": event.module,
        "day_offset": event.day_offset,
        "observed_at": event.observed_at,
        "actor": event.actor,
    }


def read_events_over_transport(
    client: FakeTelemetryEventsClient, account_slug: str, as_of_day: int
) -> list[dict[str, Any]]:
    """Thin reader: issue the request, parse the wire payload into plain
    dicts shaped identically to ``_event_wire_shape`` -- the same shape the
    in-process ``telemetry_events`` module produces, so a consumer cannot
    tell the two apart."""

    req = HttpRequest(
        method="GET",
        url=f"{EVENTS_ENDPOINT}?account={account_slug}&as_of_day={as_of_day}",
        headers={},
    )
    resp = client.send(req)
    if resp.status != 200:
        raise RuntimeError(f"fake telemetry transport returned {resp.status} for {account_slug}")
    return list(resp.json()["events"])  # type: ignore[index]


def build_telemetry_simulated_live_artifact(*, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    client = FakeTelemetryEventsClient()
    per_account: dict[str, Any] = {}
    for slug, checkpoints in _CHECKPOINTS.items():
        as_of = max(checkpoints)
        wire_events = read_events_over_transport(client, slug, as_of)
        in_process = telemetry_events_through_day(slug, as_of, sample_days=_sample_days(as_of, slug))
        wire_ids = sorted(e["event_id"] for e in wire_events)
        process_ids = sorted(e.event_id for e in in_process)
        per_account[slug] = {
            "as_of_day": as_of,
            "wire_event_count": len(wire_events),
            "in_process_event_count": len(in_process),
            "wire_matches_in_process": wire_ids == process_ids,
        }

    artifact = {
        "artifact": "telemetry_simulated_live",
        "generated_by": "eval.telemetry_simulated_live",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
        },
        "measurement_scope": (
            "Event-level login/feature_action/api_call telemetry for Pinehill "
            "Transport and Meridian Fleet Group, served over a local fake "
            "transport and read back via a thin reader, proving the wire "
            "shape and the in-process derivation agree."
        ),
        "transport": "FakeTelemetryEventsClient",
        "endpoint": EVENTS_ENDPOINT,
        "accounts": per_account,
        "requests_on_fake_transport": len(client.requests),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_telemetry_simulated_live_artifact(output_path=args.output)
    ok = all(acc["wire_matches_in_process"] for acc in artifact["accounts"].values())
    print(json.dumps({
        "artifact": str(args.output),
        "accounts": list(artifact["accounts"]),
        "all_wire_matches_in_process": ok,
    }, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
