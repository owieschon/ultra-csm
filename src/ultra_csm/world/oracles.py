"""Latent-truth and knowability audits for the living world."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ultra_csm.world.generator import WorldBuildResult
from ultra_csm.world.graph import ContextGraph


def build_oracle_report(result: WorldBuildResult, graph: ContextGraph) -> dict[str, Any]:
    latent_by_id = {row.account_id: row for row in result.latent_truth}
    doomed = [row.account_id for row in result.latent_truth if row.doomed]
    decisions_by_id = {row.account_id: row for row in result.surface_decisions}

    false_negatives = [account_id for account_id in doomed if not decisions_by_id[account_id].surfaced]
    recovered = 0
    for account_id, decision in decisions_by_id.items():
        latent = latent_by_id[account_id]
        if not decision.surfaced:
            continue
        if latent.doomed and any(key in {"health.band", "cases.open"} for key in decision.consulted_fact_keys):
            recovered += 1
        elif latent.thriving and any(key in {"adoption.rate"} for key in decision.consulted_fact_keys):
            recovered += 1

    abstained = sum(1 for row in result.surface_decisions if row.abstained)
    return {
        "artifact": "living_world_oracles",
        "schema_version": 1,
        "n_accounts": len(result.surface_decisions),
        "n_doomed": len(doomed),
        "false_negative_rate_vs_latent_truth": (
            round(len(false_negatives) / len(doomed), 4) if doomed else 0.0
        ),
        "false_negative_accounts": false_negatives[:10],
        "causal_path_recovery_rate": round(recovered / len(result.surface_decisions), 4),
        "abstention_rate": round(abstained / len(result.surface_decisions), 4),
        "graph_sections": graph.section_counts(),
    }


def run_knowability_audit(
    result: WorldBuildResult,
    graph: ContextGraph,
    *,
    planted_violation: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    failures: list[str] = []

    for decision in result.surface_decisions:
        if any("latent" in key or "truth" in key for key in decision.consulted_fact_keys):
            failures.append(f"surface_decision_leaks_latent_key:{decision.account_id}")
        if any("latent" in evidence_id for evidence_id in decision.evidence_ids):
            failures.append(f"surface_decision_leaks_latent_evidence:{decision.account_id}")

    fact_ids = {fact.fact_id for fact in graph.bitemporal_spine}
    for decision in graph.decisions:
        missing = [fact_id for fact_id in decision.consulted_fact_ids if fact_id not in fact_ids]
        if missing:
            failures.append(f"decision_points_to_missing_fact:{decision.account_id}")

    failures.extend(_agent_blindness_failures(root))
    failures.extend(_observable_latent_string_failures(result))

    if planted_violation:
        failures.append("planted_violation:latent_truth_imported_into_surface_path")

    return {
        "artifact": "knowability_audit",
        "schema_version": 1,
        "structural_agent_blindness": not any(
            failure.startswith("agent_imports_world:") for failure in failures
        ),
        "graph_consultation_integrity": not any(
            failure.startswith("decision_points_to_missing_fact:") for failure in failures
        ),
        "observable_free_of_latent_strings": not any(
            failure.startswith("observable_leaks_latent_string:") for failure in failures
        ),
        "planted_violation": planted_violation,
        "hard_ok": not failures,
        "hard_failures": failures,
    }


# Latent vocabulary that must never appear in an observable (agent-readable)
# field. The generic band-derived driver strings and neutral CTA text are
# deliberately excluded; these tokens only ever originate from latent truth.
_LATENT_TOKENS = (
    "doomed",
    "thriving",
    "conflicted",
    "champion_disengaged",
    "healthy_champion",
    "product_fit_gap",
    "fit_confirmed",
    "no_major_org_change",
    "org_change",
    "latent",
)


def _observable_latent_string_failures(result: "WorldBuildResult") -> list[str]:
    """Semantic knowability check (beyond name-matching): no latent enum or
    label string may appear in an observable text field an agent can read.
    Catches the health.drivers / CTA-reason class of leak that a structural
    import scan cannot see."""
    failures: list[str] = []

    def scan(account_id: str, where: str, text: str) -> None:
        lowered = text.lower()
        if any(token in lowered for token in _LATENT_TOKENS):
            failures.append(f"observable_leaks_latent_string:{where}:{account_id}")

    for health in result.data.health_scores:
        for driver in health.drivers:
            scan(health.account_id, "health.drivers", driver)
    for cta in result.data.ctas:
        scan(cta.account_id, "cta.reason", cta.reason)
    for case in result.data.cases:
        scan(case.account_id, "case.subject", case.subject)
    return sorted(set(failures))


def _agent_blindness_failures(repo_root: Path) -> list[str]:
    failures: list[str] = []
    agent_root = repo_root / "src" / "ultra_csm" / "agent1"
    if not agent_root.exists():
        return failures
    for path in sorted(agent_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("ultra_csm.world"):
                        failures.append(f"agent_imports_world:{path.relative_to(repo_root)}")
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("ultra_csm.world"):
                    failures.append(f"agent_imports_world:{path.relative_to(repo_root)}")
    return sorted(set(failures))
