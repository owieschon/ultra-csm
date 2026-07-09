"""Context-graph core for the living-world substrate."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ultra_csm.data_plane.contracts import CRMContact
from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.world.generator import WorldBuildResult


@dataclass(frozen=True)
class GraphFact:
    fact_id: str
    account_id: str
    fact_key: str
    value: str
    observed_at: str
    valid_at: str
    source_id: str | None


@dataclass(frozen=True)
class GraphDecision:
    decision_id: str
    account_id: str
    disposition: str
    surfaced: bool
    abstained: bool
    consulted_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphHook:
    hook_id: str
    account_id: str
    decision_id: str
    hook_kind: str
    target_metric: str
    due_by: str


@dataclass(frozen=True)
class GraphSupersedence:
    prior_fact_id: str
    current_fact_id: str
    reason: str


@dataclass(frozen=True)
class GraphIdentity:
    identity_id: str
    account_id: str
    resolution: str
    candidate_contact_ids: tuple[str, ...]
    key: str


@dataclass(frozen=True)
class GraphConflict:
    conflict_id: str
    account_id: str
    conflict_type: str
    fact_ids: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class ContextGraph:
    bitemporal_spine: tuple[GraphFact, ...]
    supersedence: tuple[GraphSupersedence, ...]
    decisions: tuple[GraphDecision, ...]
    closed_loop_hooks: tuple[GraphHook, ...]
    identity_resolution: tuple[GraphIdentity, ...]
    conflict_nodes: tuple[GraphConflict, ...]

    def section_counts(self) -> dict[str, int]:
        return {
            "bitemporal_spine": len(self.bitemporal_spine),
            "supersedence": len(self.supersedence),
            "decision_nodes": len(self.decisions),
            "closed_loop_hooks": len(self.closed_loop_hooks),
            "identity_resolution": len(self.identity_resolution),
            "conflict_nodes": len(self.conflict_nodes),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "bitemporal_spine": [asdict(row) for row in self.bitemporal_spine],
            "supersedence": [asdict(row) for row in self.supersedence],
            "decisions": [asdict(row) for row in self.decisions],
            "closed_loop_hooks": [asdict(row) for row in self.closed_loop_hooks],
            "identity_resolution": [asdict(row) for row in self.identity_resolution],
            "conflict_nodes": [asdict(row) for row in self.conflict_nodes],
        }


def build_context_graph(result: WorldBuildResult) -> ContextGraph:
    latent_by_id = {row.account_id: row for row in result.latent_truth}
    health_by_id = {row.account_id: row for row in result.data.health_scores}
    adoption_by_id = {row.account_id: row for row in result.data.adoption_summaries}
    usage_by_id = {}
    case_by_id = {}
    contacts_by_id: dict[str, list[CRMContact]] = {}
    for signal in result.data.usage_signals:
        usage_by_id.setdefault(signal.account_id, []).append(signal)
    for case in result.data.cases:
        case_by_id.setdefault(case.account_id, []).append(case)
    for contact in result.data.contacts:
        contacts_by_id.setdefault(contact.account_id, []).append(contact)

    spine: list[GraphFact] = []
    supersedence: list[GraphSupersedence] = []
    identities: list[GraphIdentity] = []
    conflicts: list[GraphConflict] = []
    decisions: list[GraphDecision] = []
    hooks: list[GraphHook] = []

    for decision in result.surface_decisions:
        account_id = decision.account_id
        latent = latent_by_id[account_id]
        health = health_by_id[account_id]
        adoption = adoption_by_id[account_id]
        usage = sorted(usage_by_id.get(account_id, []), key=lambda row: row.signal_id)
        cases = sorted(case_by_id.get(account_id, []), key=lambda row: row.case_id)
        contacts = sorted(contacts_by_id.get(account_id, []), key=lambda row: row.contact_id)

        health_fact = GraphFact(
            fact_id=det_id("graph-fact", account_id, "health"),
            account_id=account_id,
            fact_key="health.band",
            value=health.band,
            observed_at=health.measured_at,
            valid_at=health.measured_at,
            source_id=account_id,
        )
        adoption_fact = GraphFact(
            fact_id=det_id("graph-fact", account_id, "adoption"),
            account_id=account_id,
            fact_key="adoption.rate",
            value=f"{adoption.adoption_rate:.4f}",
            observed_at=adoption.measured_at,
            valid_at=adoption.measured_at,
            source_id=account_id,
        )
        case_count = sum(1 for case in cases if case.closed_at is None)
        case_fact = GraphFact(
            fact_id=det_id("graph-fact", account_id, "cases"),
            account_id=account_id,
            fact_key="cases.open",
            value=str(case_count),
            observed_at=cases[0].created_at if cases else health.measured_at,
            valid_at=health.measured_at,
            source_id=cases[0].case_id if cases else None,
        )
        usage_value = next(
            (signal for signal in usage if signal.metric_name == "daily_active_assets"),
            usage[0] if usage else None,
        )
        usage_fact = GraphFact(
            fact_id=det_id("graph-fact", account_id, "usage"),
            account_id=account_id,
            fact_key="usage.active_assets",
            value=str(int(usage_value.value)) if usage_value is not None else "0",
            observed_at=usage_value.observed_at if usage_value is not None else health.measured_at,
            valid_at=usage_value.observed_at if usage_value is not None else health.measured_at,
            source_id=usage_value.signal_id if usage_value is not None else None,
        )
        spine.extend((health_fact, adoption_fact, case_fact, usage_fact))

        if "stale_field" in latent.corruption_flags:
            stale_fact = GraphFact(
                fact_id=det_id("graph-fact", account_id, "health-stale"),
                account_id=account_id,
                fact_key="health.band",
                value="green" if health.band != "green" else "yellow",
                observed_at="2026-05-01T00:00:00Z",
                valid_at="2026-05-01T00:00:00Z",
                source_id=account_id,
            )
            spine.append(stale_fact)
            supersedence.append(
                GraphSupersedence(
                    prior_fact_id=stale_fact.fact_id,
                    current_fact_id=health_fact.fact_id,
                    reason="fresher_measurement",
                )
            )

        if contacts:
            by_email: dict[str, list[CRMContact]] = {}
            for contact in contacts:
                by_email.setdefault(contact.email, []).append(contact)
            for email, matches in sorted(by_email.items()):
                identities.append(
                    GraphIdentity(
                        identity_id=det_id("graph-identity", account_id, email),
                        account_id=account_id,
                        resolution="ambiguous" if len(matches) > 1 else "exactly_one",
                        candidate_contact_ids=tuple(contact.contact_id for contact in matches),
                        key=email,
                    )
                )

        if "duplicate_contact" in latent.corruption_flags:
            conflicts.append(
                GraphConflict(
                    conflict_id=det_id("graph-conflict", account_id, "duplicate_contact"),
                    account_id=account_id,
                    conflict_type="duplicate_contact",
                    fact_ids=tuple(
                        identity.identity_id
                        for identity in identities
                        if identity.account_id == account_id and identity.resolution == "ambiguous"
                    ),
                    status="open",
                )
            )
        if "mislinked_case" in latent.corruption_flags or (
            health.band == "green" and case_count > 0 and decision.surfaced
        ):
            conflicts.append(
                GraphConflict(
                    conflict_id=det_id("graph-conflict", account_id, "surface_conflict"),
                    account_id=account_id,
                    conflict_type="surface_conflict",
                    fact_ids=(health_fact.fact_id, case_fact.fact_id),
                    status="open",
                )
            )

        consulted_fact_ids = (health_fact.fact_id, adoption_fact.fact_id, case_fact.fact_id, usage_fact.fact_id)
        decisions.append(
            GraphDecision(
                decision_id=decision.decision_id,
                account_id=account_id,
                disposition=decision.disposition,
                surfaced=decision.surfaced,
                abstained=decision.abstained,
                consulted_fact_ids=consulted_fact_ids,
            )
        )
        hooks.append(
            GraphHook(
                hook_id=det_id("graph-hook", account_id, decision.decision_id),
                account_id=account_id,
                decision_id=decision.decision_id,
                hook_kind="follow_up" if decision.surfaced else "watchful_waiting",
                target_metric="adoption.rate" if decision.surfaced else "health.band",
                due_by="2026-07-05",
            )
        )

    return ContextGraph(
        bitemporal_spine=tuple(spine),
        supersedence=tuple(supersedence),
        decisions=tuple(decisions),
        closed_loop_hooks=tuple(hooks),
        identity_resolution=tuple(identities),
        conflict_nodes=tuple(conflicts),
    )
