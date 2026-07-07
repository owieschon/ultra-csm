"""Centralize-shaped app usage and PostHog telemetry exhaust.

This module adds a source-specific telemetry layer for the six named
``fleetops`` universe arcs. It mirrors the existing event-level product
telemetry discipline: raw events are causal exhaust of the bible/scripted
arcs, and agent-facing ``UsageSignal`` rows are derived from those events
rather than authored as a second usage story.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ultra_csm.data_plane.contracts import UsageSignal
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import rfc3339

PropertyValue = str | int | float | bool
Properties = tuple[tuple[str, PropertyValue], ...]


def _det_int(*parts: object) -> int:
    return UUID(det_id(*parts)).int


def _props(**kwargs: PropertyValue) -> Properties:
    return tuple(sorted(kwargs.items()))


@dataclass(frozen=True)
class ArcTelemetryProfile:
    account_slug: str
    arc: str
    checkpoint_days: tuple[int, ...]
    centralize_truth: str
    posthog_truth: str


@dataclass(frozen=True)
class CentralizeAppEvent:
    """One Centralize-domain event from app/backend/extension surfaces."""

    event_id: str
    account_id: str
    user_id: str
    event_type: str
    feature: str
    route: str
    object_type: str
    object_id: str
    day_offset: int
    observed_at: str
    source_ref: str
    confidence: str
    properties: Properties = ()


@dataclass(frozen=True)
class CentralizePostHogEvent:
    """One PostHog-shaped raw event emitted from Centralize app surfaces."""

    event_id: str
    account_id: str | None
    distinct_id: str
    session_id: str
    event: str
    current_url: str
    day_offset: int
    observed_at: str
    replay_ref: str | None
    contains_console_logs: bool
    contains_exception: bool
    confidence: str
    properties: Properties = ()


@dataclass(frozen=True)
class CentralizeTelemetryBundle:
    account_slug: str
    day_offset: int
    app_events: tuple[CentralizeAppEvent, ...]
    posthog_events: tuple[CentralizePostHogEvent, ...]
    usage_signals: tuple[UsageSignal, ...]


CENTRALIZE_ARC_PROFILES: dict[str, ArcTelemetryProfile] = {
    "pinehill-transport": ArcTelemetryProfile(
        account_slug="pinehill-transport",
        arc="onboarding_stall",
        checkpoint_days=(20, 50, 310),
        centralize_truth="legacy dispatch integration blocks activation until late recovery",
        posthog_truth="support-heavy sessions show sync failures, exceptions, and slow network timing",
    ),
    "pinnacle-supply": ArcTelemetryProfile(
        account_slug="pinnacle-supply",
        arc="single_threaded_risk",
        checkpoint_days=(10, 120, 250),
        centralize_truth="relationship map stays narrow until a second stakeholder appears",
        posthog_truth="low-error app sessions expose repeated champion/contact views",
    ),
    "quarrystone-logistics": ArcTelemetryProfile(
        account_slug="quarrystone-logistics",
        arc="churn_brewing",
        checkpoint_days=(30, 190, 225),
        centralize_truth="known red account remains unworked and eventually churns",
        posthog_truth="near-absence of meaningful app usage is the signal",
    ),
    "aspenridge-supply": ArcTelemetryProfile(
        account_slug="aspenridge-supply",
        arc="silent_decline",
        checkpoint_days=(90, 200, 340),
        centralize_truth="usage declines while relationship/comms stay calm",
        posthog_truth="quiet pageview/autocapture decay without errors or support pressure",
    ),
    "meridian-fleet": ArcTelemetryProfile(
        account_slug="meridian-fleet",
        arc="expansion_ready",
        checkpoint_days=(20, 170, 280),
        centralize_truth="multi-threaded growth and facilities stakeholder activity precede ARR expansion",
        posthog_truth="high-intent sessions cluster around relationships, opportunities, and account plans",
    ),
    "trailhead-logistics": ArcTelemetryProfile(
        account_slug="trailhead-logistics",
        arc="healthy_control",
        checkpoint_days=(60, 180, 300),
        centralize_truth="steady exemplary adoption with no risk or expansion trigger",
        posthog_truth="boring healthy telemetry: steady usage, few errors, no anomalous replay evidence",
    ),
}


_USERS_BY_ARC = {
    "onboarding_stall": ("csm-102", "usr_centralize_support_engineer"),
    "single_threaded_risk": ("csm-101", "usr_centralize_growth_csm"),
    "churn_brewing": ("csm-104", "usr_centralize_renewals"),
    "silent_decline": ("csm-102", "usr_centralize_growth_csm"),
    "expansion_ready": ("csm-101", "usr_centralize_expansion"),
    "healthy_control": ("csm-101", "usr_centralize_advocacy"),
}


def centralize_telemetry_bundle(account_slug: str, day_offset: int) -> CentralizeTelemetryBundle:
    if account_slug not in CENTRALIZE_ARC_PROFILES:
        raise ValueError(f"Centralize telemetry is not scripted for {account_slug!r}")
    app_events = centralize_app_events_for_day(account_slug, day_offset)
    posthog_events = centralize_posthog_events_for_day(account_slug, day_offset)
    return CentralizeTelemetryBundle(
        account_slug=account_slug,
        day_offset=day_offset,
        app_events=app_events,
        posthog_events=posthog_events,
        usage_signals=centralize_usage_signals_for_day(account_slug, day_offset),
    )


def centralize_app_events_for_day(
    account_slug: str, day_offset: int
) -> tuple[CentralizeAppEvent, ...]:
    profile = CENTRALIZE_ARC_PROFILES[account_slug]
    account_id = account_id_for(account_slug)
    primary_user, secondary_user = _USERS_BY_ARC[profile.arc]
    events: list[CentralizeAppEvent] = []

    def add(
        event_type: str,
        feature: str,
        route: str,
        object_type: str,
        object_slug: str,
        hour: int,
        user_id: str = primary_user,
        confidence: str = "synthetic_truth",
        **properties: PropertyValue,
    ) -> None:
        events.append(
            CentralizeAppEvent(
                event_id=det_id(
                    "centralize-app-event",
                    account_id,
                    day_offset,
                    event_type,
                    feature,
                    object_slug,
                    hour,
                ),
                account_id=account_id,
                user_id=user_id,
                event_type=event_type,
                feature=feature,
                route=route,
                object_type=object_type,
                object_id=det_id("centralize-object", account_id, object_slug),
                day_offset=day_offset,
                observed_at=rfc3339(day_offset, hour),
                source_ref="centralize_app:mcp_api_simulated",
                confidence=confidence,
                properties=_props(**properties),
            )
        )

    add(
        "account_viewed",
        "account_workspace",
        f"/account/{account_id}",
        "account",
        "account",
        9,
        lifecycle_arc=profile.arc,
    )

    if profile.arc == "onboarding_stall":
        severity = "recovered" if day_offset >= 300 else "active_blocker"
        failure_count = 0 if day_offset >= 300 else (7 if day_offset >= 50 else 2)
        add(
            "integration_sync_reviewed",
            "integration_status",
            f"/account/{account_id}/engagement",
            "integration",
            "legacy-dispatch",
            10,
            user_id=secondary_user,
            sync_status="failing" if failure_count else "healthy",
            failure_count=failure_count,
            blocker_state=severity,
        )
        add(
            "account_plan_updated",
            "account_plan",
            f"/account/{account_id}/plan/onboarding",
            "plan",
            "legacy-integration-plan",
            11,
            milestone="legacy_dispatch_bridge",
            status="complete" if day_offset >= 300 else "at_risk",
        )
        if failure_count:
            add(
                "support_case_linked",
                "support_context",
                f"/account/{account_id}/notes",
                "case",
                f"legacy-dispatch-day-{day_offset}",
                12,
                user_id=secondary_user,
                priority="high",
                repeat_topic=True,
            )

    elif profile.arc == "single_threaded_risk":
        width = 2 if day_offset >= 120 else 1
        strength = "strong" if day_offset >= 240 else "weak"
        add(
            "relationship_map_viewed",
            "relationship_map",
            f"/account/{account_id}/relationships",
            "relationship_map",
            "map",
            10,
            stakeholder_width=width,
            strongest_relationship=strength,
        )
        add(
            "contact_profile_opened",
            "contacts",
            f"/contact/{det_id('person', account_id, 'champion')}",
            "contact",
            "primary-champion",
            11,
            contact_role="champion",
            engagement_state="quiet" if day_offset < 120 else "rebalancing",
        )
        if day_offset >= 120:
            add(
                "contact_added_to_map",
                "relationship_map",
                f"/account/{account_id}/relationships",
                "contact",
                "monica-reeves",
                12,
                contact_role="vp_supply_chain_operations",
            )

    elif profile.arc == "churn_brewing":
        add(
            "health_record_viewed",
            "health",
            f"/account/{account_id}/reporting",
            "health_score",
            "red-health",
            10,
            current_band="red",
            acted=False,
        )
        if day_offset >= 190:
            add(
                "renewal_case_viewed",
                "renewal",
                f"/account/{account_id}/engagement",
                "case",
                "renewal-no-response",
                11,
                response_state="unanswered",
            )

    elif profile.arc == "silent_decline":
        add(
            "usage_report_viewed",
            "usage_reporting",
            f"/account/{account_id}/reporting",
            "usage_report",
            "adoption-trend",
            10,
            trend="declining",
            health_band="green",
        )
        if day_offset >= 200:
            add(
                "saved_view_opened",
                "accounts",
                "/accounts",
                "saved_view",
                "green-accounts",
                11,
                misleading_surface=True,
            )

    elif profile.arc == "expansion_ready":
        add(
            "relationship_map_updated",
            "relationship_map",
            f"/account/{account_id}/relationships",
            "relationship_map",
            "facilities-thread",
            10,
            stakeholder_width=2,
            department_count=2,
        )
        add(
            "opportunity_viewed",
            "opportunities",
            f"/opportunity/{det_id('opp', account_id, 'expansion')}",
            "opportunity",
            "expansion",
            11,
            stage="pre_close" if day_offset < 180 else "closed_won",
        )
        add(
            "recommended_action_completed",
            "recommended_actions",
            f"/account/{account_id}/actions",
            "recommended_action",
            "expansion-readiness",
            12,
            action="multi_threaded_expansion_brief",
        )

    elif profile.arc == "healthy_control":
        add(
            "relationship_map_viewed",
            "relationship_map",
            f"/account/{account_id}/relationships",
            "relationship_map",
            "map",
            10,
            stakeholder_width=4,
            strongest_relationship="strong",
        )
        add(
            "report_exported",
            "reporting",
            f"/account/{account_id}/reporting",
            "report",
            "qbr-adoption",
            11,
            report_type="qbr_adoption",
            risk_flag=False,
        )

    for idx in range(_extra_app_event_count(profile.arc, day_offset)):
        event_type, feature, route_suffix, object_type = _extra_app_event(profile.arc, idx)
        add(
            event_type,
            feature,
            route_suffix.format(account_id=account_id),
            object_type,
            f"{event_type}-{idx}",
            13 + idx % 7,
            confidence="inferred_route",
            noise_class="realistic_app_exhaust",
            lifecycle_arc=profile.arc,
        )

    return tuple(events)


def centralize_posthog_events_for_day(
    account_slug: str, day_offset: int
) -> tuple[CentralizePostHogEvent, ...]:
    profile = CENTRALIZE_ARC_PROFILES[account_slug]
    account_id = account_id_for(account_slug)
    user_id = _USERS_BY_ARC[profile.arc][0]
    distinct_id = det_id("posthog-person", user_id)
    base_path = _dominant_path(account_id, profile.arc)
    events: list[CentralizePostHogEvent] = []

    def add(
        event: str,
        hour: int,
        path: str = base_path,
        session_index: int = 0,
        contains_console_logs: bool = False,
        contains_exception: bool = False,
        account_known: bool = True,
        confidence: str = "observed_config",
        **properties: PropertyValue,
    ) -> None:
        session_id = det_id("posthog-session", account_id, day_offset, session_index)
        replay_ref = f"posthog:recording:{session_id}"
        events.append(
            CentralizePostHogEvent(
                event_id=det_id("centralize-posthog-event", session_id, event, hour, path),
                account_id=account_id if account_known else None,
                distinct_id=distinct_id,
                session_id=session_id,
                event=event,
                current_url=f"https://app.usecentralize.com{path}",
                day_offset=day_offset,
                observed_at=rfc3339(day_offset, hour),
                replay_ref=replay_ref,
                contains_console_logs=contains_console_logs,
                contains_exception=contains_exception,
                confidence=confidence,
                properties=_props(
                    **{
                        "$session_id": session_id,
                        "$pathname": path,
                        "$browser": "Chrome",
                        "organization_id": "org_fleetops",
                        "centralize_account_id": account_id,
                        **properties,
                    }
                ),
            )
        )

    add("$pageview", 9, posthog_surface="web_app")
    add("$autocapture", 10, element="button", text=_dominant_action(profile.arc))

    if profile.arc == "onboarding_stall" and day_offset < 300:
        add(
            "$exception",
            10,
            contains_console_logs=True,
            contains_exception=True,
            exception_type="TRPCClientError",
            exception_message="Legacy dispatch sync timed out",
            network_timing_ms=2500 if day_offset >= 50 else 1450,
        )
        add(
            "centralize.integration_sync_failed",
            11,
            confidence="inferred_route",
            integration="legacy_dispatch",
            failure_count=7 if day_offset >= 50 else 2,
        )
    elif profile.arc == "churn_brewing" and day_offset >= 190:
        add(
            "$pageview",
            11,
            path=f"/account/{account_id}/engagement",
            confidence="observed_config",
            engagement="renewal_case",
        )
    elif profile.arc == "silent_decline":
        add(
            "$autocapture",
            11,
            path=f"/account/{account_id}/reporting",
            confidence="inferred_route",
            element="tab",
            text="Usage",
            network_timing_ms=620,
        )
    elif profile.arc == "expansion_ready":
        add(
            "centralize.relationship_map_updated",
            11,
            confidence="inferred_route",
            stakeholder_width=2,
            department_count=2,
        )
        add(
            "centralize.recommended_action_completed",
            12,
            path=f"/account/{account_id}/actions",
            confidence="inferred_route",
            action="multi_threaded_expansion_brief",
        )
    elif profile.arc == "healthy_control":
        add(
            "$autocapture",
            11,
            path=f"/account/{account_id}/reporting",
            element="button",
            text="Export",
            network_timing_ms=410,
        )
    elif profile.arc == "single_threaded_risk":
        add(
            "$autocapture",
            11,
            path=f"/account/{account_id}/relationships",
            confidence="inferred_route",
            element="node",
            text="Champion",
            stakeholder_width=2 if day_offset >= 120 else 1,
        )

    if _det_int("posthog-missing-account", account_id, day_offset) % 7 == 0:
        add(
            "$autocapture",
            13,
            account_known=False,
            confidence="observed_config",
            element="svg",
            text="relationship-map-canvas",
        )

    for session_index in range(1, _posthog_session_count(profile.arc, day_offset)):
        path = _session_path(account_id, profile.arc, session_index)
        missing_identity = _det_int("posthog-identity-gap", account_id, day_offset, session_index) % 9 == 0
        network_timing_ms = _network_timing_ms(profile.arc, day_offset, session_index)
        add(
            "$pageview",
            8 + session_index % 10,
            path=path,
            session_index=session_index,
            account_known=not missing_identity,
            posthog_surface="web_app",
            network_timing_ms=network_timing_ms,
        )
        add(
            "$autocapture",
            9 + session_index % 10,
            path=path,
            session_index=session_index,
            account_known=not missing_identity,
            element=_autocapture_element(profile.arc, session_index),
            text=_autocapture_text(profile.arc, session_index),
            network_timing_ms=network_timing_ms,
        )
        if _has_console_log(profile.arc, day_offset, session_index):
            add(
                "$console_log",
                10 + session_index % 10,
                path=path,
                session_index=session_index,
                contains_console_logs=True,
                account_known=not missing_identity,
                level="warn",
                message_class=_console_message_class(profile.arc),
            )

    return tuple(events)


def centralize_usage_signals_for_day(account_slug: str, day_offset: int) -> tuple[UsageSignal, ...]:
    app_events = centralize_app_events_for_day(account_slug, day_offset)
    posthog_events = centralize_posthog_events_for_day(account_slug, day_offset)
    account_id = account_id_for(account_slug)
    observed_at = rfc3339(day_offset, 23)
    metrics = {
        "centralize_account_views": sum(e.event_type == "account_viewed" for e in app_events),
        "centralize_relationship_events": sum("relationship" in e.feature for e in app_events),
        "centralize_action_completions": sum(
            e.event_type == "recommended_action_completed" for e in app_events
        ),
        "centralize_integration_sync_failures": sum(
            e.event_type == "integration_sync_reviewed"
            and dict(e.properties).get("sync_status") == "failing"
            for e in app_events
        ),
        "posthog_session_recordings": len({e.session_id for e in posthog_events if e.replay_ref}),
        "posthog_frontend_exceptions": sum(e.contains_exception for e in posthog_events),
        "posthog_autocapture_events": sum(e.event == "$autocapture" for e in posthog_events),
    }
    return tuple(
        UsageSignal(
            signal_id=det_id("centralize-usage-signal", account_id, metric_name, day_offset),
            account_id=account_id,
            grain="company",
            subject_id=None,
            metric_name=metric_name,
            value=float(value),
            unit="events",
            observed_at=observed_at,
            source_ref="centralize_posthog:derived_fixture",
        )
        for metric_name, value in sorted(metrics.items())
    )


def centralize_usage_signals_through_day(
    account_slug: str, as_of_day: int, *, sample_days: tuple[int, ...] | None = None
) -> tuple[UsageSignal, ...]:
    if account_slug not in CENTRALIZE_ARC_PROFILES:
        raise ValueError(f"Centralize telemetry is not scripted for {account_slug!r}")
    days = sample_days if sample_days is not None else CENTRALIZE_ARC_PROFILES[account_slug].checkpoint_days
    signals: list[UsageSignal] = []
    for day in days:
        if day <= as_of_day:
            signals.extend(centralize_usage_signals_for_day(account_slug, day))
    return tuple(signals)


def centralize_sample_days(account_slug: str, as_of_day: int) -> tuple[int, ...]:
    """Bounded but faithful sample grid for raw telemetry exports.

    Real PostHog exports are dense; the repo fixture stays bounded by sampling
    every two weeks, then pinning each arc's checkpoints and important beat
    days so the story turns are always present.
    """

    if account_slug not in CENTRALIZE_ARC_PROFILES:
        raise ValueError(f"Centralize telemetry is not scripted for {account_slug!r}")
    profile = CENTRALIZE_ARC_PROFILES[account_slug]
    days = set(range(0, as_of_day + 1, 14))
    days.update(day for day in profile.checkpoint_days if day <= as_of_day)
    days.update(day for day in _ARC_BEAT_DAYS[profile.arc] if day <= as_of_day)
    days.add(0)
    return tuple(sorted(days))


def centralize_telemetry_timeline(
    account_slug: str, as_of_day: int, *, sample_days: tuple[int, ...] | None = None
) -> tuple[CentralizeTelemetryBundle, ...]:
    days = sample_days if sample_days is not None else centralize_sample_days(account_slug, as_of_day)
    return tuple(centralize_telemetry_bundle(account_slug, day) for day in days if day <= as_of_day)


def _dominant_path(account_id: str, arc: str) -> str:
    if arc in {"single_threaded_risk", "expansion_ready", "healthy_control"}:
        return f"/account/{account_id}/relationships"
    if arc in {"silent_decline", "churn_brewing"}:
        return f"/account/{account_id}/reporting"
    return f"/account/{account_id}/engagement"


def _dominant_action(arc: str) -> str:
    return {
        "onboarding_stall": "Review sync failure",
        "single_threaded_risk": "Open champion profile",
        "churn_brewing": "Open renewal case",
        "silent_decline": "Open usage report",
        "expansion_ready": "Complete recommended action",
        "healthy_control": "Export QBR report",
    }[arc]


_ARC_BEAT_DAYS: dict[str, tuple[int, ...]] = {
    "onboarding_stall": (7, 30, 35, 50, 80, 100, 300),
    "single_threaded_risk": (3, 14, 110, 120, 130, 240),
    "churn_brewing": (30, 160, 190, 220, 225),
    "silent_decline": (90, 150, 200, 300, 340),
    "expansion_ready": (10, 14, 120, 170, 180, 270, 280),
    "healthy_control": (60, 80, 165, 180, 270, 300),
}


_EXTRA_APP_EVENTS: tuple[tuple[str, str, str, str], ...] = (
    ("saved_view_opened", "accounts", "/accounts", "saved_view"),
    ("contact_search_performed", "contacts", "/contacts", "search"),
    ("note_viewed", "notes", "/account/{account_id}/notes", "note"),
    ("tag_filter_applied", "contacts", "/contacts", "tag_filter"),
    ("activity_feed_scrolled", "engagement", "/account/{account_id}/engagement", "feed"),
    ("chart_node_expanded", "relationship_map", "/account/{account_id}/relationships", "node"),
    ("account_export_previewed", "reporting", "/account/{account_id}/reporting", "export"),
)


def _extra_app_event_count(arc: str, day_offset: int) -> int:
    if arc == "onboarding_stall":
        if day_offset < 100:
            return 4
        return 1 if day_offset >= 300 else 2
    if arc == "single_threaded_risk":
        return 2 if day_offset < 110 else 4
    if arc == "churn_brewing":
        if day_offset >= 220:
            return 0
        return 1 if day_offset < 160 else 2
    if arc == "silent_decline":
        return 4 if day_offset <= 90 else (2 if day_offset <= 220 else 1)
    if arc == "expansion_ready":
        return 5 if 120 <= day_offset <= 190 else 3
    if arc == "healthy_control":
        return 3
    raise ValueError(f"unknown Centralize telemetry arc {arc!r}")


def _extra_app_event(arc: str, index: int) -> tuple[str, str, str, str]:
    if arc == "expansion_ready":
        rotation = (
            ("opportunity_stage_inspected", "opportunities", "/opportunities", "opportunity"),
            ("buying_role_viewed", "relationship_map", "/account/{account_id}/relationships", "buying_role"),
            ("account_plan_section_viewed", "account_plan", "/account/{account_id}/plan/expansion", "plan"),
            *_EXTRA_APP_EVENTS,
        )
    elif arc == "onboarding_stall":
        rotation = (
            ("integration_retry_opened", "integration_status", "/account/{account_id}/engagement", "integration"),
            ("support_timeline_filtered", "support_context", "/account/{account_id}/notes", "case"),
            *_EXTRA_APP_EVENTS,
        )
    elif arc == "churn_brewing":
        rotation = (
            ("renewal_case_viewed", "renewal", "/account/{account_id}/engagement", "case"),
            ("health_record_viewed", "health", "/account/{account_id}/reporting", "health_score"),
            *_EXTRA_APP_EVENTS,
        )
    else:
        rotation = _EXTRA_APP_EVENTS
    return rotation[index % len(rotation)]


def _posthog_session_count(arc: str, day_offset: int) -> int:
    if arc == "onboarding_stall":
        if day_offset < 100:
            return 7
        return 3 if day_offset < 300 else 2
    if arc == "single_threaded_risk":
        return 3 if day_offset < 110 else 5
    if arc == "churn_brewing":
        if day_offset >= 220:
            return 1
        return 1 if day_offset < 160 else 2
    if arc == "silent_decline":
        if day_offset <= 90:
            return 5
        return 3 if day_offset <= 220 else 2
    if arc == "expansion_ready":
        return 8 if 120 <= day_offset <= 190 else 5
    if arc == "healthy_control":
        return 4
    raise ValueError(f"unknown Centralize telemetry arc {arc!r}")


def _session_path(account_id: str, arc: str, session_index: int) -> str:
    paths = {
        "onboarding_stall": (
            f"/account/{account_id}/engagement",
            f"/account/{account_id}/notes",
            f"/account/{account_id}/plan/onboarding",
        ),
        "single_threaded_risk": (
            f"/account/{account_id}/relationships",
            f"/contact/{det_id('person', account_id, 'champion')}",
            f"/account/{account_id}/contacts",
        ),
        "churn_brewing": (
            f"/account/{account_id}/reporting",
            f"/account/{account_id}/engagement",
        ),
        "silent_decline": (
            f"/account/{account_id}/reporting",
            "/accounts",
            f"/account/{account_id}/engagement",
        ),
        "expansion_ready": (
            f"/account/{account_id}/relationships",
            f"/opportunity/{det_id('opp', account_id, 'expansion')}",
            f"/account/{account_id}/actions",
            f"/account/{account_id}/plan/expansion",
        ),
        "healthy_control": (
            f"/account/{account_id}/relationships",
            f"/account/{account_id}/reporting",
            f"/account/{account_id}/engagement",
        ),
    }[arc]
    return paths[session_index % len(paths)]


def _network_timing_ms(arc: str, day_offset: int, session_index: int) -> int:
    base = {
        "onboarding_stall": 1800 if day_offset < 100 else 850,
        "single_threaded_risk": 620,
        "churn_brewing": 540,
        "silent_decline": 580,
        "expansion_ready": 720,
        "healthy_control": 430,
    }[arc]
    jitter = _det_int("centralize-network-jitter", arc, day_offset, session_index) % 240
    return base + jitter


def _autocapture_element(arc: str, session_index: int) -> str:
    if arc in {"single_threaded_risk", "expansion_ready"}:
        return ("button", "svg", "node", "menuitem")[session_index % 4]
    return ("button", "tab", "link", "input")[session_index % 4]


def _autocapture_text(arc: str, session_index: int) -> str:
    labels = {
        "onboarding_stall": ("Retry sync", "Open case", "Filter timeline", "Update plan"),
        "single_threaded_risk": ("Champion", "Add contact", "Relationship map", "Contacts"),
        "churn_brewing": ("Health", "Renewal", "Engagement", "Open case"),
        "silent_decline": ("Usage", "Green accounts", "Trend", "Report"),
        "expansion_ready": ("Opportunity", "Buying roles", "Complete action", "Expansion plan"),
        "healthy_control": ("Export", "QBR", "Relationships", "Engagement"),
    }[arc]
    return labels[session_index % len(labels)]


def _has_console_log(arc: str, day_offset: int, session_index: int) -> bool:
    if arc == "onboarding_stall" and day_offset < 100:
        return session_index % 2 == 0
    if arc == "expansion_ready":
        return session_index == 3 and day_offset in {170, 180}
    return _det_int("centralize-console-log", arc, day_offset, session_index) % 23 == 0


def _console_message_class(arc: str) -> str:
    return {
        "onboarding_stall": "integration_sync_retry_warning",
        "single_threaded_risk": "relationship_graph_render_notice",
        "churn_brewing": "low_activity_noop",
        "silent_decline": "usage_report_loaded",
        "expansion_ready": "org_chart_canvas_warning",
        "healthy_control": "benign_export_notice",
    }[arc]
