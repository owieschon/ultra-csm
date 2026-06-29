"""Minimal governance plane for the CSM agent."""

from ultra_csm.governance.authorizer import (
    Authorizer,
    PERM_ORDER_CONFIRM,
    ROLE_CS_ORCHESTRATOR,
    ROLE_ORDER_CONFIRM_AUTHORITY,
    canonical_payload_sha256,
    make_principal,
    permission_id,
    role_id,
    seed_roster,
)
from ultra_csm.governance.csm_actions import (
    CSM_ACTION_SPECS,
    CSMActionSpec,
    UnknownCSMActionError,
    csm_action_spec,
    proposal_fields_for,
)
from ultra_csm.governance.gate import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    GateError,
    GateOutcome,
    Verdict,
    VerdictSource,
)

__all__ = [
    "Authorizer", "canonical_payload_sha256",
    "seed_roster", "make_principal", "role_id", "permission_id",
    "PERM_ORDER_CONFIRM", "ROLE_CS_ORCHESTRATOR", "ROLE_ORDER_CONFIRM_AUTHORITY",
    "CSM_ACTION_SPECS", "CSMActionSpec", "UnknownCSMActionError",
    "csm_action_spec", "proposal_fields_for",
    "ActionGate", "ActionProposal", "GateOutcome", "Verdict", "VerdictSource",
    "FixtureVerdictSource", "GateError",
]
