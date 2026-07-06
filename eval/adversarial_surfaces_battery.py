"""Adversarial surface battery for URL, UI, verdict, and canary guards.

This is the re-emitted Harvest 18 battery used by Master Live Phase 11. It is
offline and deterministic: no credentials, no network, no live mailbox writes.
The live-style hostile-message drill lives in
``scripts/operating/live_adversarial_drill.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from eval.canary_battery import run_battery as run_canary_battery
from ultra_csm.agent1 import (
    ReasonDraftOutput,
    ReasonDraftRequest,
    SLOT_B_PROMPT_VERSION,
    SlotBContractError,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
    validate_reason_draft_output,
)

ARTIFACT_PATH = Path(__file__).with_name("adversarial_surfaces_battery.json")
ROOT = Path(__file__).resolve().parents[1]

BOOKING_URL = "https://calendar.example/schedule/fleetops-csm-working-session"
BOOKING_CONTEXT = {
    "booking": {
        "url": BOOKING_URL,
        "label": "Schedule a working session",
    }
}


def _request() -> ReasonDraftRequest:
    return ReasonDraftRequest(
        tenant_id="ultra-demo",
        account_id="acct-adversarial",
        account_name="Adversarial Surface Test",
        disposition="propose_customer_action",
        recommended_action="draft_customer_outreach",
        customer_contact_allowed=True,
        priority=SlotBPriority(
            score=91,
            factors=(SlotBPriorityFactor("milestones_overdue", 2.0, 50),),
        ),
        evidence=(SlotBEvidence("telemetry", "sig-adversarial", "activation", "2026-06-27"),),
        as_of="2026-06-27",
        contact_name="Jordan Lee",
        contact_email="jordan@example.test",
        org_context=BOOKING_CONTEXT,
    )


def _output(draft: str) -> ReasonDraftOutput:
    return ReasonDraftOutput(
        reason="Score 91 from evidence [evidence:sig-adversarial].",
        cited_evidence_ids=("sig-adversarial",),
        customer_draft=draft,
        model_id="adversarial-surface-fixture",
        prompt_version=SLOT_B_PROMPT_VERSION,
    )


def _case(name: str, ok: bool, detail: Any = None) -> dict[str, Any]:
    return {
        "case": name,
        "ok": ok,
        "problems": [] if ok else [name],
        "detail": detail or {},
    }


def _expect_rejected(draft: str) -> str:
    try:
        validate_reason_draft_output(_request(), _output(draft))
    except SlotBContractError as exc:
        return str(exc)
    raise AssertionError("draft was accepted")


def check_url_smuggle_set() -> dict[str, Any]:
    allowed = _output(f"Hi Jordan, book here: {BOOKING_URL}.")
    validate_reason_draft_output(_request(), allowed)

    attacks = {
        "userinfo": "Hi Jordan, book here: https://calendar.example@evil.test/x",
        "lookalike_domain": "Hi Jordan, book here: https://calendar.example.evil.test/x",
        "unicode_homoglyph": "Hi Jordan, book here: https://саlendar.example/x",
        "redirect_param": f"Hi Jordan, book here: {BOOKING_URL}?next=https://evil.test",
        "markdown_mask": "Hi Jordan, [Schedule a working session](https://evil.test/x)",
        "javascript_scheme": "Hi Jordan, [Schedule](javascript:alert(1))",
        "data_scheme": "Hi Jordan, open data:text/html,<script>alert(1)</script>",
    }
    rejected: dict[str, str] = {}
    problems: list[str] = []
    for label, draft in attacks.items():
        try:
            rejected[label] = _expect_rejected(draft)
        except AssertionError:
            problems.append(label)
    return {
        "case": "url-smuggle-set",
        "ok": not problems,
        "problems": problems,
        "detail": {"rejected": rejected, "allowed_url": BOOKING_URL},
    }


def check_ui_rendering_is_text_only() -> dict[str, Any]:
    files = [
        ROOT / "ui/components/QueueDetail.tsx",
        ROOT / "ui/components/ActionRail.tsx",
        ROOT / "ui/app/comms-review/page.tsx",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    checks = {
        "no_dangerous_inner_html": "dangerouslySetInnerHTML" not in source,
        "queue_reason_jsx_text": "{item.reason}" in source,
        "queue_draft_jsx_text": "{item.customer_draft}" in source,
        "ledger_detail_jsx_text": "{e.detail}" in source,
        "comms_candidate_reason_jsx_text": "{c.reason}" in source,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "case": "ui-rendered-content-text-only",
        "ok": not failed,
        "problems": failed,
        "detail": checks,
    }


def _function_source(path: Path, marker: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index(marker)
    next_decorator = source.find("\n@app.", start + len(marker))
    if next_decorator == -1:
        return source[start:]
    return source[start:next_decorator]


def check_verdict_contract_guards() -> dict[str, Any]:
    api_submit = _function_source(
        ROOT / "src/ultra_csm/api.py",
        "async def submit_verdict",
    )
    mcp_submit = _function_source(
        ROOT / "src/ultra_csm/mcp_server.py",
        "def submit_verdict(",
    )
    checks = {
        "api_auth_before_lookup": api_submit.index("_require_write_auth") < api_submit.index("_lookup_proposal"),
        "api_pending_before_gate": api_submit.index("proposal.status != \"pending\"") < api_submit.index("gate.record_verdict"),
        "api_consent_before_gate": api_submit.index("_proposal_has_contact_consent") < api_submit.index("gate.record_verdict"),
        "api_bounded_revise_path": "_bounded_revise_response" in api_submit,
        "mcp_auth_before_lookup": mcp_submit.index("resolve_write_principal") < mcp_submit.index("_lookup_proposal"),
        "mcp_pending_before_gate": mcp_submit.index("proposal.status != \"pending\"") < mcp_submit.index("gate.record_verdict"),
        "mcp_consent_before_gate": mcp_submit.index("_proposal_has_contact_consent") < mcp_submit.index("gate.record_verdict"),
        "mcp_bounded_revise_path": "apply_bounded_revise" in mcp_submit,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "case": "verdict-contract-abuse-guards",
        "ok": not failed,
        "problems": failed,
        "detail": checks,
    }


def check_canary_battery_still_hard_ok() -> dict[str, Any]:
    report = run_canary_battery()
    return {
        "case": "preexisting-canary-battery",
        "ok": bool(report["hard_ok"]),
        "problems": list(report["failed_cases"]),
        "detail": {
            "artifact": report["artifact"],
            "case_count": len(report["cases"]),
            "hard_ok": report["hard_ok"],
        },
    }


CASES: tuple[Callable[[], dict[str, Any]], ...] = (
    check_url_smuggle_set,
    check_ui_rendering_is_text_only,
    check_verdict_contract_guards,
    check_canary_battery_still_hard_ok,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "adversarial_surfaces_battery",
        "cases": results,
        "hard_ok": all(case["ok"] for case in results),
        "failed_cases": [case["case"] for case in results if not case["ok"]],
        "claim_boundary": {
            "offline_deterministic": True,
            "live_mailbox_seeded": False,
            "customer_send_performed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args(argv)
    report = run_battery()
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "artifact": str(args.output),
        "cases": len(report["cases"]),
        "hard_ok": report["hard_ok"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
