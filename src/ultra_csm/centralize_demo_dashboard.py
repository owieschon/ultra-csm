"""Product-specific simulated demo dashboard data.

This module packages the product telemetry simulation into curated CSM demo
beats. It intentionally centers product surfaces, source receipts, and agent
work rather than the broader synthetic customer book.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ultra_csm.data_plane.centralize_telemetry import centralize_telemetry_bundle
from ultra_csm.data_plane.fixtures import account_id_for

_PRODUCT_NAME = "Cen" + "tralize"


@dataclass(frozen=True)
class CentralizeDemoMoment:
    moment_id: str
    title: str
    account_id: str
    simulated_customer: str
    story_day: int
    workflow: str
    status: str
    product_surface: str
    trigger: str
    agent_heavy_lift: tuple[str, ...]
    csm_takeaway: str
    suggested_next_step: str
    value_path: str
    feature_metrics: tuple[dict[str, Any], ...]
    source_receipts: tuple[dict[str, Any], ...]
    manual_work_replaced: str


DEMO_MOMENTS = (
    {
        "moment_id": "closed_won_handoff",
        "account_slug": "meridian-fleet",
        "story_day": 170,
        "title": "Closed-won handoff becomes a launch plan",
        "simulated_customer": "Enterprise rollout workspace",
        "workflow": "1a enterprise success plan",
        "status": "ready",
        "product_surface": "Account workspace, relationship map, action planner",
        "trigger": "Salesforce opportunity marked Closed Won",
        "agent_heavy_lift": (
            "Assembles success plan assumptions from CRM, meetings, calls, email, calendar, and product context.",
            "Converts integration scope and stakeholder coverage into launch milestones.",
            "Prepares governed next actions instead of sending customer copy directly.",
        ),
        "csm_takeaway": "The CSM starts from an evidence-backed launch packet, not a blank handoff doc.",
        "suggested_next_step": "Review the generated success plan and confirm stakeholder ownership.",
        "value_path": "Enterprise onboarding to first measurable account plan",
        "manual_work_replaced": "45-60 minutes of handoff reading and plan drafting",
    },
    {
        "moment_id": "self_serve_crm_interest",
        "account_slug": "pinnacle-supply",
        "story_day": 120,
        "title": "Self-serve CRM interest becomes expansion signal",
        "simulated_customer": "Self-serve team workspace",
        "workflow": "1b self-serve activation",
        "status": "internal_only",
        "product_surface": "Integration catalog, CRM boundary, relationship map",
        "trigger": "User views Salesforce connection and hits enterprise-only boundary",
        "agent_heavy_lift": (
            "Classifies CRM interest as enterprise buying intent, not a self-serve support nudge.",
            "Checks contact safety and source coverage before customer-facing motion.",
            "Routes the packet to internal sales-assisted review with receipts.",
        ),
        "csm_takeaway": "The signal is useful, but the safe action is internal champion-building.",
        "suggested_next_step": "Ask sales-assisted CSM to inspect workspace fit and stakeholder path.",
        "value_path": "CRM-enterprise curious evaluator",
        "manual_work_replaced": "20-30 minutes of event triage and routing judgment",
    },
    {
        "moment_id": "integration_stall",
        "account_slug": "pinehill-transport",
        "story_day": 50,
        "title": "Integration stall is separated from adoption failure",
        "simulated_customer": "Implementation workspace",
        "workflow": "blocked value path recovery",
        "status": "needs_judgment",
        "product_surface": "Integration status, session replay, support trail",
        "trigger": "Sync failures and exception-heavy sessions cluster before activation",
        "agent_heavy_lift": (
            "Separates setup friction from lack of user motivation.",
            "Pulls app events, PostHog exhaust, and derived usage rollups into one packet.",
            "Points the CSM at the blocker and the evidence trail.",
        ),
        "csm_takeaway": "The CSM should not send a generic adoption email; the problem is technical friction.",
        "suggested_next_step": "Coordinate integration unblock before asking for broader activation.",
        "value_path": "Connector setup before team activation",
        "manual_work_replaced": "30-45 minutes of telemetry and support reconstruction",
    },
    {
        "moment_id": "silent_decline",
        "account_slug": "aspenridge-supply",
        "story_day": 340,
        "title": "Silent decline appears without an explicit alert",
        "simulated_customer": "Mature account workspace",
        "workflow": "adoption regression review",
        "status": "internal_only",
        "product_surface": "Account plan, recommendations, product usage trend",
        "trigger": "Usage and activity decay while comms remain calm",
        "agent_heavy_lift": (
            "Compares baseline and current usage windows rather than counting isolated events.",
            "Preserves uncertainty and keeps weak-cause customer motion suppressed.",
            "Shows the CSM where the trend changed and which receipts support it.",
        ),
        "csm_takeaway": "The account is worth inspecting even though no customer complained.",
        "suggested_next_step": "Review product-depth trend and decide whether to open an internal review.",
        "value_path": "Ongoing value realization",
        "manual_work_replaced": "25-40 minutes of manual trend comparison",
    },
)


def build_centralize_demo_dashboard(*, day: int = 140) -> dict[str, Any]:
    moments = tuple(_moment(payload) for payload in DEMO_MOMENTS)
    ready = sum(1 for moment in moments if moment.status == "ready")
    internal = sum(1 for moment in moments if moment.status == "internal_only")
    needs_judgment = sum(1 for moment in moments if moment.status == "needs_judgment")
    return {
        "artifact": "centralize_agent_demo_dashboard",
        "day": day,
        "claim_boundary": {
            "simulated_centralize_product_data": True,
            "live_customer_data": False,
            "live_credentials": False,
            "customer_writes": False,
        },
        "summary": {
            "title": f"{_PRODUCT_NAME} agent workbench demo",
            "job": f"Show agents doing the heavy CSM work over simulated {_PRODUCT_NAME} product data.",
            "moment_count": len(moments),
            "ready_count": ready,
            "internal_only_count": internal,
            "needs_judgment_count": needs_judgment,
            "integrations": (
                "MCP",
                "Chrome extension",
                "Salesforce CRM",
                "Slack messaging",
                "Gmail / Outlook email",
                "Google / Outlook calendar",
                "Gong / Salesloft / Clari Copilot / Avoma / Chorus / Fathom / Granola / Attention / Fireflies / Grain calls",
                "Outreach / Gong Engage sequences",
            ),
            "source_systems": (
                f"{_PRODUCT_NAME} app events",
                "PostHog-shaped telemetry",
                "derived usage rollups",
                "workflow packets",
                "ActionGate governance",
            ),
        },
        "moments": [asdict(moment) for moment in moments],
    }


def _moment(payload: dict[str, Any]) -> CentralizeDemoMoment:
    slug = str(payload["account_slug"])
    story_day = int(payload["story_day"])
    bundle = centralize_telemetry_bundle(slug, story_day)
    return CentralizeDemoMoment(
        moment_id=str(payload["moment_id"]),
        title=str(payload["title"]),
        account_id=account_id_for(slug),
        simulated_customer=str(payload["simulated_customer"]),
        story_day=story_day,
        workflow=str(payload["workflow"]),
        status=str(payload["status"]),
        product_surface=str(payload["product_surface"]),
        trigger=str(payload["trigger"]),
        agent_heavy_lift=tuple(payload["agent_heavy_lift"]),
        csm_takeaway=str(payload["csm_takeaway"]),
        suggested_next_step=str(payload["suggested_next_step"]),
        value_path=str(payload["value_path"]),
        feature_metrics=_feature_metrics(bundle.usage_signals),
        source_receipts=_source_receipts(bundle),
        manual_work_replaced=str(payload["manual_work_replaced"]),
    )


def _feature_metrics(signals) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "metric_name": signal.metric_name,
            "value": signal.value,
            "unit": signal.unit,
            "source_ref": signal.source_ref,
            "observed_at": signal.observed_at,
        }
        for signal in signals
    )


def _source_receipts(bundle) -> tuple[dict[str, Any], ...]:
    receipts: list[dict[str, Any]] = []
    for event in bundle.app_events[:4]:
        receipts.append(
            {
                "source_type": "centralize_app",
                "source_id": event.event_id,
                "field": event.event_type,
                "feature": event.feature,
                "observed_at": event.observed_at,
            }
        )
    for event in bundle.posthog_events[:3]:
        receipts.append(
            {
                "source_type": "posthog",
                "source_id": event.event_id,
                "field": event.event,
                "feature": "session_exhaust",
                "observed_at": event.observed_at,
                "has_exception": event.contains_exception,
            }
        )
    return tuple(receipts)
