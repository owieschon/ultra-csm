"""CSMWorkPacket contract and planner tests."""

from __future__ import annotations

import pytest

httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402
from ultra_csm.data_plane.contracts import CRMAccount  # noqa: E402
from ultra_csm.work_packets import FEEDBACK_CATEGORIES, build_coverage_packet  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer work-packet-token"}
IRONHORSE = "f16ceec8-7a3a-5d9d-a0ee-a2e7f119fc43"


@pytest.fixture(scope="module")
def client():
    env = pytest.MonkeyPatch()
    env.setenv("ULTRA_CSM_API_TOKENS", "work-packet-token:Work Packet Tester")
    env.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        env.undo()


@pytest.fixture(scope="module")
def day140_sweep(client: TestClient):
    resp = client.post("/sweep?day=140", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    return resp.json()


def _packets(sweep: dict) -> list[dict]:
    packets = [item["work_packet"] for item in sweep["work_items"]]
    packets.extend(item["work_packet"] for item in sweep["escalations"])
    packets.extend(sweep["coverage_packets"])
    return packets


def _ironhorse_packet(sweep: dict) -> dict:
    return next(
        item["work_packet"]
        for item in sweep["work_items"]
        if item["account_id"] == IRONHORSE
    )


def test_every_visible_work_item_has_packet(day140_sweep: dict):
    visible = day140_sweep["work_items"] + day140_sweep["escalations"]
    assert visible
    for item in visible:
        assert item.get("work_packet"), item


def test_packet_schema_has_required_operator_fields(day140_sweep: dict):
    required = {
        "packet_id",
        "account_id",
        "account_name",
        "generated_at",
        "as_of_day",
        "cadence",
        "job_type",
        "lane",
        "primary_next_step",
        "why_now",
        "diagnostic_hypothesis",
        "implied_customer_state",
        "recommended_action",
        "contact_plan",
        "prepared_artifacts",
        "allowed_ctas",
        "governance",
        "evidence_chain",
        "bucket_trace",
        "coverage_trace",
        "open_questions",
        "confidence",
        "feedback_hooks",
    }
    for packet in _packets(day140_sweep):
        assert required <= set(packet), packet["packet_id"]
        assert packet["primary_next_step"]
        assert packet["recommended_action"]["label"]


def test_ironhorse_packet_has_specific_blocker_contact_and_action(day140_sweep: dict):
    packet = _ironhorse_packet(day140_sweep)
    text = " ".join(
        [
            packet["primary_next_step"],
            packet["diagnostic_hypothesis"]["summary"],
            packet["recommended_action"]["message_strategy"],
            packet["prepared_artifacts"][0]["body_or_outline"],
        ]
    ).lower()
    assert "gps hardware compatibility" in text
    assert "50% asset activation" in text or "asset activation" in text
    assert packet["contact_plan"]["primary_contact"]["name"] == "Marcus Webb"
    assert packet["contact_plan"]["backup_contact"]["name"] == "Lisa Chang"
    assert packet["governance"]["requires_action_gate"] is True
    assert packet["governance"]["can_execute_from_ui"] is False
    assert "review overdue activation steps" not in text


def test_no_motion_action_contradictions(day140_sweep: dict):
    for item in day140_sweep["work_items"]:
        packet = item["work_packet"]
        artifact_types = {artifact["artifact_type"] for artifact in packet["prepared_artifacts"]}
        if packet["job_type"] == "education_recommendation":
            assert "education_recommendation" in artifact_types
        if packet["job_type"] == "customer_outreach":
            assert "email_draft" in artifact_types
        if packet["lane"] == "needs_judgment":
            assert any(cta["kind"] in {"approve", "inspect", "leave_feedback"} for cta in packet["allowed_ctas"])


def test_confident_packet_requires_evidence_chain(day140_sweep: dict):
    for packet in _packets(day140_sweep):
        if packet["confidence"] >= 0.5 and packet["job_type"] != "needs_data":
            assert packet["evidence_chain"], packet["packet_id"]
            assert packet["diagnostic_hypothesis"]["source_ids"], packet["packet_id"]


def test_unsupported_recommendation_becomes_needs_data():
    account = CRMAccount(
        account_id="missing-data-account",
        name="Missing Data Account",
        owner_id="csm-1",
        industry=None,
    )

    class EmptyCS:
        def get_company(self, account_id):  # noqa: ANN001
            return None

        def get_health_score(self, account_id):  # noqa: ANN001
            return None

        def get_adoption_summary(self, account_id):  # noqa: ANN001
            return None

    class EmptyPlane:
        cs = EmptyCS()

    packet = build_coverage_packet(
        account=account,
        as_of="2026-06-27",
        book_size=1,
        accounts_scanned=1,
        included_work_account_ids=frozenset(),
        data_plane=EmptyPlane(),  # type: ignore[arg-type]
    )
    assert packet.job_type == "needs_data"
    assert packet.lane == "blocked"
    assert packet.evidence_chain == ()


def test_governed_ctas_require_action_gate_metadata(day140_sweep: dict):
    for packet in _packets(day140_sweep):
        for cta in packet["allowed_ctas"]:
            if cta["kind"] in {"approve", "edit", "assign", "simulate", "deep_link"}:
                assert cta["governance_requirement"], cta
                assert cta["enabled"] is False or packet["governance"]["requires_action_gate"]


def test_readonly_demo_ctas_are_non_executing(day140_sweep: dict):
    for packet in _packets(day140_sweep):
        assert packet["governance"]["can_execute_from_ui"] is False
        for cta in packet["allowed_ctas"]:
            assert cta["readonly_behavior"]
            if cta["kind"] == "approve":
                assert cta["enabled"] is False


def test_every_packet_has_bucket_trace(day140_sweep: dict):
    for packet in _packets(day140_sweep):
        trace = packet["bucket_trace"]
        assert trace["rule_id"]
        assert trace["rule_label"]
        assert trace["thresholds"]
        assert trace["matched"]


def test_coverage_trace_accounts_for_book(day140_sweep: dict):
    packets = _packets(day140_sweep)
    assert day140_sweep["coverage_packets"]
    for packet in packets:
        trace = packet["coverage_trace"]
        assert trace["book_size"] == len(day140_sweep["swept_accounts"])
        assert trace["accounts_scanned"] == len(day140_sweep["swept_accounts"])


def test_suppressed_or_monitoring_accounts_are_explainable(day140_sweep: dict):
    coverage_packets = day140_sweep["coverage_packets"]
    assert coverage_packets
    for packet in coverage_packets:
        assert packet["lane"] in {"covered", "blocked", "monitoring", "suppressed"}
        assert packet["coverage_trace"]["excluded_or_suppressed_reason"]
        assert any(cta["kind"] in {"inspect", "leave_feedback"} for cta in packet["allowed_ctas"])


def test_feedback_categories_cover_operator_corrections(day140_sweep: dict):
    packet = _ironhorse_packet(day140_sweep)
    categories = {hook["category"] for hook in packet["feedback_hooks"]}
    assert set(FEEDBACK_CATEGORIES) <= categories


def test_feedback_does_not_execute_external_write(day140_sweep: dict):
    for packet in _packets(day140_sweep):
        for hook in packet["feedback_hooks"]:
            assert hook["local_only"] is True
            assert "does not approve or execute" in hook["readonly_behavior"]


def test_product_and_education_packets_require_customer_experience_evidence(day140_sweep: dict):
    selected = [
        packet for packet in _packets(day140_sweep)
        if packet["job_type"] in {"product_feedback_synthesis", "education_recommendation"}
    ]
    assert selected
    for packet in selected:
        assert packet["evidence_chain"], packet["packet_id"]
        assert packet["recommended_action"]["source_ids"], packet["packet_id"]
