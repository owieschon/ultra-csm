"""Declarative metadata for Agent 1 lenses."""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.governance.csm_actions import CSMActionType


@dataclass(frozen=True)
class LensSpec:
    """Stable lens contract: triggers, factors, actions, and prompt version."""

    lens_id: str
    lens_version: str
    trigger_subscriptions: tuple[str, ...]
    factor_profile: tuple[str, ...]
    action_bindings: tuple[CSMActionType, ...]
    prompt_version: str
    customer_facing: bool
    claim_boundary: str
