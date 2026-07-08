from __future__ import annotations

from fastapi.testclient import TestClient

from ultra_csm.api import app
from ultra_csm.centralize_demo_dashboard import build_centralize_demo_dashboard

PRODUCT_NAME = "Cen" + "tralize"


def test_centralize_demo_dashboard_centers_product_data_not_generic_book():
    dashboard = build_centralize_demo_dashboard(day=140)

    assert dashboard["artifact"] == "centralize_agent_demo_dashboard"
    assert dashboard["claim_boundary"] == {
        "simulated_centralize_product_data": True,
        "live_customer_data": False,
        "live_credentials": False,
        "customer_writes": False,
    }
    assert dashboard["summary"]["moment_count"] == 4
    assert {
        f"{PRODUCT_NAME} app events",
        "PostHog-shaped telemetry",
        "derived usage rollups",
        "workflow packets",
        "ActionGate governance",
    } <= set(dashboard["summary"]["source_systems"])
    assert "MCP" in dashboard["summary"]["integrations"]
    assert any("Gong" in item for item in dashboard["summary"]["integrations"])

    moments = {moment["moment_id"]: moment for moment in dashboard["moments"]}
    assert {
        "closed_won_handoff",
        "self_serve_crm_interest",
        "integration_stall",
        "silent_decline",
    } == set(moments)
    for moment in moments.values():
        assert moment["feature_metrics"]
        assert moment["source_receipts"]
        assert PRODUCT_NAME not in moment["simulated_customer"]
        assert moment["manual_work_replaced"]


def test_centralize_demo_dashboard_endpoint_is_read_only_simulated_payload():
    with TestClient(app) as client:
        response = client.get("/centralize/demo-dashboard?day=140")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact"] == "centralize_agent_demo_dashboard"
    assert body["day"] == 140
    assert len(body["moments"]) == 4
    assert body["claim_boundary"]["simulated_centralize_product_data"] is True
    assert body["claim_boundary"]["customer_writes"] is False
