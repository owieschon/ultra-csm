"""Aggregate struggle-trigger signals across the book into an ARR-aware,
coverage-gap-ranked content roadmap.

Reuses ``agent1.sweep``'s existing per-account trigger computation
(``_account_tier_and_triggers``) and ``collapse_cohorts``'s book-iteration
pattern rather than re-deriving either. Tenant scope is fleetops +
loopway only (Decision 3, ``19_CONTENT_ROADMAP.md``): fieldstone/
crateworks have no CS-platform records and ``_slot_b_inputs_for_account``
fails closed for them, so they would contribute zero triggers.

Deviation from the dispatch's literal Decision 4 wording, recorded here
per K2: ``collapse_cohorts`` tier-buckets its (trigger, tier) grouping
because it decides which cohort to COLLAPSE into one proposal. This
roadmap's Notion schema (Decision 5) has no per-tier column -- Gap x
Tenant only -- so a tier sub-bucket has no observable effect on the
output. Implemented as a straight per-tenant, per-trigger account count
instead of routing through ``resolve_motions``/``PlaybookSet``, which
would add a knowledge-tenant-slug dependency for zero schema benefit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.agent1.content_route_matcher import load_tenant_content_catalog
from ultra_csm.agent1.sweep import _account_tier_and_triggers
from ultra_csm.data_plane.contracts import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
)
from ultra_csm.value_model import (
    ValueModelConfig,
    account_attributes,
    load_value_model_config,
    resolve_thresholds,
)

TENANTS: tuple[str, ...] = ("fleetops", "loopway")

# All 7 struggle triggers _account_tier_and_triggers can fire (agent1/sweep.py).
KNOWN_TRIGGERS: tuple[str, ...] = (
    "champion_inactive",
    "feature_shallow_depth",
    "health_red",
    "health_yellow",
    "milestones_overdue",
    "low_seat_penetration",
    "outcome_unknown",
)

# Both tenants' synthetic books share the same seed anchor (verified: both
# tenants/loopway/synthetic_book.py and the root synthetic_book.py define
# SEED_DATE = "2026-06-21"). IF/THEN (recorded in report): a first pass at
# day 0 (no simulation) showed fleetops entirely flat -- 0 accounts
# affected on every trigger, an artifact of the demo book's day-0
# baseline being uniformly healthy, not a real "no demand" finding
# (verified: a live sweep earlier this session, day_offset=140, showed
# real fleetops accounts -- e.g. Ironhorse Freight Co -- hitting
# milestones_overdue/health signals). Fixed by applying
# ``book_simulator.simulate_book`` (a data-plane module, NOT an api.py
# dependency -- api.py merely calls the same function) at day_offset=140
# for fleetops, landing on 2026-11-08, the exact day already verified
# live to produce real signal. Loopway's book already showed real signal
# at day 0 with no evidence of its own day-simulation mechanism, so it
# stays at day 0 -- not forced onto fleetops's offset for symmetry alone.
FLEETOPS_DAY_OFFSET = 140
FLEETOPS_AS_OF = "2026-11-08"
LOOPWAY_AS_OF = "2026-06-21"

# CRM data-plane tenant_id differs from the knowledge-tenant slug used for
# content_catalog.json paths and Notion display -- profile quirk, verified
# the hard way: list_accounts(tenant_id="fleetops") silently returns 0
# accounts (empty, not an error) because fleetops's book is seeded under
# the CRM identity "ultra-demo" (DEFAULT_TENANT). RoadmapRow.tenant stays
# the knowledge-slug ("fleetops"/"loopway") for catalog lookup + display;
# this map is ONLY for the data-plane connector/list_accounts call.
_CRM_TENANT_ID = {"fleetops": "ultra-demo", "loopway": "loopway"}


@dataclass(frozen=True)
class RoadmapRow:
    tenant: str
    gap: str
    accounts_affected: int
    high_arr_bonus: int
    existing_content_count: int
    coverage_gap_score: int


def _build_tenant_data_plane(tenant: str) -> tuple[CustomerDataPlane, str]:
    """Returns (data_plane, as_of) -- coupled, since a simulated day's
    mutations and the as_of used for milestone-overdue checks must agree."""

    if tenant == "fleetops":
        from ultra_csm.data_plane.book_simulator import simulate_book
        from ultra_csm.data_plane.synthetic_book import build_synthetic_book

        base = build_synthetic_book()
        data = simulate_book(base, day_offset=FLEETOPS_DAY_OFFSET)
        return (
            CustomerDataPlane(
                crm=FixtureCRMDataConnector(tenant=_CRM_TENANT_ID["fleetops"], data=data),
                cs=FixtureCSPlatformConnector(data=data),
                telemetry=FixtureProductTelemetryConnector(data=data),
            ),
            FLEETOPS_AS_OF,
        )
    if tenant == "loopway":
        from ultra_csm.data_plane.tenants.loopway.synthetic_book import (
            build_synthetic_book as build_loopway_book,
        )

        data = build_loopway_book()
        return (
            CustomerDataPlane(
                crm=FixtureCRMDataConnector(tenant=_CRM_TENANT_ID["loopway"], data=data),
                cs=FixtureCSPlatformConnector(data=data),
                telemetry=FixtureProductTelemetryConnector(data=data),
            ),
            LOOPWAY_AS_OF,
        )
    raise ValueError(f"content_roadmap only covers {TENANTS!r}, got {tenant!r}")


def _tenant_rows(
    tenant: str, *, value_model_config: ValueModelConfig
) -> tuple[RoadmapRow, ...]:
    data_plane, as_of = _build_tenant_data_plane(tenant)
    accounts = tuple(data_plane.crm.list_accounts(tenant_id=_CRM_TENANT_ID[tenant]))

    accounts_by_trigger: dict[str, set[str]] = {t: set() for t in KNOWN_TRIGGERS}
    high_arr_by_trigger: dict[str, set[str]] = {t: set() for t in KNOWN_TRIGGERS}

    for account in accounts:
        tier_and_triggers = _account_tier_and_triggers(
            data_plane, account, value_model_config=value_model_config, as_of=as_of
        )
        if tier_and_triggers is None:
            continue
        _tier, triggers = tier_and_triggers
        company = data_plane.cs.get_company(account.account_id)
        # arr_review_floor_cents is resolved per-account (most-specific-wins
        # rule match, e.g. "high_arr_review_default" vs "base_default" --
        # verified live: a real sweep this session showed both rule names),
        # never a single global config value -- mirrors exactly how
        # value_model.py's own _ttv_base_factors resolves it.
        is_high_arr = company is not None and (
            company.arr_cents
            >= resolve_thresholds(
                account_attributes(account, company), value_model_config
            ).thresholds.arr_review_floor_cents
        )
        for trigger in triggers:
            if trigger not in accounts_by_trigger:
                continue
            accounts_by_trigger[trigger].add(account.account_id)
            if is_high_arr:
                high_arr_by_trigger[trigger].add(account.account_id)

    catalog = load_tenant_content_catalog(tenant)
    existing_count_by_gap: dict[str, int] = {}
    for entry in catalog:
        existing_count_by_gap[entry.addresses_gap] = existing_count_by_gap.get(entry.addresses_gap, 0) + 1

    return score_rows(tenant, accounts_by_trigger, high_arr_by_trigger, existing_count_by_gap)


def score_rows(
    tenant: str,
    accounts_by_trigger: dict[str, set[str]],
    high_arr_by_trigger: dict[str, set[str]],
    existing_count_by_gap: dict[str, int],
) -> tuple[RoadmapRow, ...]:
    """Pure scoring arithmetic (Decision 4), separated from book iteration
    so it is directly unit-testable against hand-constructed dicts rather
    than a full synthetic ``CustomerDataPlane`` fixture."""

    rows = []
    for trigger in KNOWN_TRIGGERS:
        accounts_affected = len(accounts_by_trigger.get(trigger, ()))
        high_arr_bonus = len(high_arr_by_trigger.get(trigger, ()))
        existing_content_count = existing_count_by_gap.get(trigger, 0)
        rows.append(
            RoadmapRow(
                tenant=tenant,
                gap=trigger,
                accounts_affected=accounts_affected,
                high_arr_bonus=high_arr_bonus,
                existing_content_count=existing_content_count,
                coverage_gap_score=accounts_affected + high_arr_bonus - existing_content_count,
            )
        )
    return tuple(rows)


def build_content_roadmap(
    *, value_model_config: ValueModelConfig | None = None
) -> tuple[RoadmapRow, ...]:
    """The ranked (tenant, gap) roadmap across TENANTS, descending by
    coverage_gap_score. Ties broken by (tenant, gap) for determinism."""

    config = value_model_config or load_value_model_config()
    rows: list[RoadmapRow] = []
    for tenant in TENANTS:
        rows.extend(_tenant_rows(tenant, value_model_config=config))
    return tuple(
        sorted(rows, key=lambda r: (-r.coverage_gap_score, r.tenant, r.gap))
    )
