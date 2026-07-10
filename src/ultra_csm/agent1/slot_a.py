"""Agent 1 Slot A: bounded case-note classification.

Slot A is intentionally narrow: one case-note text becomes one enum label. It does
not call tools or connectors, and the validator owns the case/account boundary.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from ultra_csm.llm_transport import resolve_message_transport

SlotAClassification = Literal["blocker", "noise", "unknown"]
ValidationMode = Literal["raise", "unknown"]

SLOT_A_SOURCE = "slot_a"
SLOT_A_PROMPT_VERSION = "agent1-slot-a-case-note-v1"
SLOT_A_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "prompts"
    / "agent1_slot_a_case_note_v1.md"
)

FIXTURE_SLOT_A_MODEL_ID = "fixture-agent1-slot-a-v1"
LIVE_SLOT_A_MODEL_ID = "claude-opus-4-8"
LIVE_TIMEOUT_S = 30.0
LIVE_MAX_RETRIES = 2

_ALLOWED_CLASSIFICATIONS = frozenset({"blocker", "noise", "unknown"})
_BLOCKER_PHRASES = (
    "activation blocked",
    "blocked activation",
    "blocked rollout",
    "blocking rollout",
    "cannot proceed",
    "can't proceed",
    "cannot complete",
    "go-live blocked",
    "gateway install cannot proceed",
    "implementation blocker",
    "install delayed",
    "required step is blocked",
    "rollout blocked",
    "unable to activate",
)
_NOISE_PHRASES = (
    "admin update",
    "billing question",
    "billing-only",
    "contact update",
    "fyi only",
    "general status update",
    "invoice contact update",
    "invoice question",
    "no action needed",
    "resolved",
)
_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore (?:policy|previous|these|this)\b", re.IGNORECASE),
    re.compile(r"\bclassify (?:this )?as\b", re.IGNORECASE),
    re.compile(r"\bmark me\b", re.IGNORECASE),
    re.compile(r"\bemail all customer data\b", re.IGNORECASE),
    re.compile(r"\bfollow (?:these|this|the) instruction", re.IGNORECASE),
    re.compile(r"\breturn (?:only )?\{", re.IGNORECASE),
)
_BLOCKED_REASON_PHRASES = (
    "ignore policy",
    "mark me top priority",
    "email all customer data",
    "classify this as",
)


@dataclass(frozen=True)
class SlotACaseRef:
    case_id: str
    account_id: str


@dataclass(frozen=True)
class CaseNoteClassificationRequest:
    tenant_id: str
    account_id: str
    case_id: str
    case_note_text: str
    account_case_refs: tuple[SlotACaseRef, ...]

    def allowed_case_ids(self) -> tuple[str, ...]:
        return tuple(
            ref.case_id
            for ref in self.account_case_refs
            if ref.account_id == self.account_id
        )


@dataclass(frozen=True)
class CaseNoteClassificationOutput:
    case_id: str
    account_id: str
    classification: str
    source: str
    model_id: str
    prompt_version: str
    cited_case_id: str
    reason: str


class SlotAContractError(ValueError):
    """Raised when a Slot A request/output violates the boundary contract."""


class CaseNoteClassifier(Protocol):
    model_id: str
    prompt_version: str

    def classify(
        self,
        request: CaseNoteClassificationRequest,
    ) -> CaseNoteClassificationOutput: ...


class FixtureCaseNoteClassifier:
    """Deterministic offline Slot A for CI and scorecards."""

    model_id = FIXTURE_SLOT_A_MODEL_ID
    prompt_version = SLOT_A_PROMPT_VERSION

    def classify(
        self,
        request: CaseNoteClassificationRequest,
    ) -> CaseNoteClassificationOutput:
        note = _trusted_note_text(request.case_note_text)
        blocker_hits = _phrase_hits(note, _BLOCKER_PHRASES)
        noise_hits = _phrase_hits(note, _NOISE_PHRASES)
        if blocker_hits and not noise_hits:
            classification: SlotAClassification = "blocker"
            reason = f"Matched blocker case-note signals: {_hit_text(blocker_hits)}."
        elif noise_hits and not blocker_hits:
            classification = "noise"
            reason = f"Matched noise case-note signals: {_hit_text(noise_hits)}."
        elif blocker_hits and noise_hits:
            classification = "unknown"
            reason = "Mixed blocker and noise signals; no safe single-label classification."
        else:
            classification = "unknown"
            reason = "No clear blocker or noise signal in the case note."

        output = CaseNoteClassificationOutput(
            case_id=request.case_id,
            account_id=request.account_id,
            classification=classification,
            source=SLOT_A_SOURCE,
            model_id=self.model_id,
            prompt_version=self.prompt_version,
            cited_case_id=request.case_id,
            reason=reason,
        )
        return validate_case_note_classification(request, output)


class UnsafeGuessingCaseNoteClassifier:
    """Deliberately bad Slot A foil used by tests and scorecards."""

    model_id = "unsafe-agent1-slot-a"
    prompt_version = SLOT_A_PROMPT_VERSION

    def classify(
        self,
        request: CaseNoteClassificationRequest,
    ) -> CaseNoteClassificationOutput:
        output = CaseNoteClassificationOutput(
            case_id=request.case_id,
            account_id=request.account_id,
            classification="blocker",
            source=SLOT_A_SOURCE,
            model_id=self.model_id,
            prompt_version=self.prompt_version,
            cited_case_id=request.case_id,
            reason="Guessed blocker despite ambiguous case-note evidence.",
        )
        return validate_case_note_classification(request, output)


class AnthropicCaseNoteClassifier:
    """Optional live Slot A. Construction is credential-gated unless a client is passed."""

    model_id = LIVE_SLOT_A_MODEL_ID
    prompt_version = SLOT_A_PROMPT_VERSION

    def __init__(
        self,
        client=None,
        *,
        transport=None,
        model_id: str | None = None,
        prompt_text: str | None = None,
    ) -> None:
        if client is None and transport is None and not os.environ.get("ANTHROPIC_API_KEY"):
            # The direct API path is still the default; the CLI transport is selected
            # structurally via ULTRA_CSM_LLM_TRANSPORT and needs no key check here.
            from ultra_csm.llm_transport import configured_transport_name

            if configured_transport_name() == "anthropic_api":
                raise SlotAContractError("live Slot A requires ANTHROPIC_API_KEY")
        self._transport = transport or resolve_message_transport(
            client=client,
            timeout_s=LIVE_TIMEOUT_S,
            max_retries=LIVE_MAX_RETRIES,
        )
        self.model_id = model_id or LIVE_SLOT_A_MODEL_ID
        self._prompt_text = prompt_text

    def classify(
        self,
        request: CaseNoteClassificationRequest,
    ) -> CaseNoteClassificationOutput:
        prompt = self._prompt_text or SLOT_A_PROMPT_PATH.read_text(encoding="utf-8")
        payload = {
            "request": _jsonable_request(request),
            "required_output_schema": {
                "case_id": "string",
                "account_id": "string",
                "classification": "blocker | noise | unknown",
                "source": "slot_a",
                "model_id": self.model_id,
                "prompt_version": self.prompt_version,
                "cited_case_id": "string",
                "reason": "string",
            },
        }
        response = self._transport.complete(
            model_id=self.model_id,
            max_tokens=300,
            system_prompt=prompt,
            user_text=json.dumps(payload, sort_keys=True),
        )
        output = _parse_live_output(
            response.text,
            model_id=self.model_id,
            prompt_version=self.prompt_version,
        )
        return validate_case_note_classification(request, output, on_error="unknown")


def validate_case_note_classification(
    request: CaseNoteClassificationRequest,
    output: CaseNoteClassificationOutput,
    *,
    on_error: ValidationMode = "raise",
) -> CaseNoteClassificationOutput:
    try:
        _validate_case_note_classification(request, output)
    except SlotAContractError as exc:
        if on_error == "unknown":
            unknown = _unknown_output(request, output.model_id or "invalid-slot-a-output", str(exc))
            _validate_case_note_classification(request, unknown)
            return unknown
        raise
    if on_error not in {"raise", "unknown"}:
        raise SlotAContractError("on_error must be 'raise' or 'unknown'")
    return output


def prompt_metadata() -> dict[str, str]:
    return {
        "prompt_version": SLOT_A_PROMPT_VERSION,
        "prompt_path": _display_prompt_path(),
        "fixture_model_id": FIXTURE_SLOT_A_MODEL_ID,
        "live_model_id": LIVE_SLOT_A_MODEL_ID,
    }


def _validate_case_note_classification(
    request: CaseNoteClassificationRequest,
    output: CaseNoteClassificationOutput,
) -> None:
    _validate_request_case(request)
    if output.source != SLOT_A_SOURCE:
        raise SlotAContractError("source must be slot_a")
    if output.prompt_version != SLOT_A_PROMPT_VERSION:
        raise SlotAContractError("unexpected prompt_version")
    if not output.model_id.strip():
        raise SlotAContractError("model_id is required")
    if output.case_id != request.case_id:
        raise SlotAContractError("output case_id must match request case_id")
    if output.account_id != request.account_id:
        raise SlotAContractError("output account_id must match request account_id")
    if output.classification not in _ALLOWED_CLASSIFICATIONS:
        raise SlotAContractError("classification must be blocker, noise, or unknown")
    if output.cited_case_id != request.case_id:
        raise SlotAContractError("cited_case_id must match request case_id")
    cited = _case_ref_for(request, output.cited_case_id)
    if cited.account_id != request.account_id:
        raise SlotAContractError("cited_case_id does not belong to account_id")
    if not output.reason.strip():
        raise SlotAContractError("reason is required")
    reason = output.reason.lower()
    for phrase in _BLOCKED_REASON_PHRASES:
        if phrase in reason:
            raise SlotAContractError(f"untrusted instruction leaked: {phrase}")


def _validate_request_case(request: CaseNoteClassificationRequest) -> None:
    if not request.account_id.strip():
        raise SlotAContractError("account_id is required")
    if not request.case_id.strip():
        raise SlotAContractError("case_id is required")
    ref = _case_ref_for(request, request.case_id)
    if ref.account_id != request.account_id:
        raise SlotAContractError("request case_id does not belong to account_id")


def _case_ref_for(
    request: CaseNoteClassificationRequest,
    case_id: str,
) -> SlotACaseRef:
    refs = tuple(ref for ref in request.account_case_refs if ref.case_id == case_id)
    if not refs:
        raise SlotAContractError(f"unknown case_id: {case_id}")
    account_ids = {ref.account_id for ref in refs}
    if len(account_ids) > 1:
        raise SlotAContractError(f"ambiguous case_id boundary: {case_id}")
    return refs[0]


def _unknown_output(
    request: CaseNoteClassificationRequest,
    model_id: str,
    reason: str,
) -> CaseNoteClassificationOutput:
    return CaseNoteClassificationOutput(
        case_id=request.case_id,
        account_id=request.account_id,
        classification="unknown",
        source=SLOT_A_SOURCE,
        model_id=model_id,
        prompt_version=SLOT_A_PROMPT_VERSION,
        cited_case_id=request.case_id,
        reason=f"Invalid Slot A output coerced to unknown: {reason}",
    )


def _parse_live_output(
    text: str,
    *,
    model_id: str,
    prompt_version: str,
) -> CaseNoteClassificationOutput:
    try:
        raw = json.loads(_extract_json_object(text))
    except json.JSONDecodeError as exc:
        raise SlotAContractError(f"live Slot A returned invalid JSON: {exc}") from exc
    for field in ("case_id", "account_id", "classification", "source", "cited_case_id", "reason"):
        if not isinstance(raw.get(field), str):
            raise SlotAContractError(f"{field} must be a string")
    return CaseNoteClassificationOutput(
        case_id=raw["case_id"],
        account_id=raw["account_id"],
        classification=raw["classification"],
        source=raw["source"],
        model_id=model_id,
        prompt_version=prompt_version,
        cited_case_id=raw["cited_case_id"],
        reason=raw["reason"],
    )


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start:end + 1]


def _text_from_message(msg) -> str:
    return "".join(
        block.text for block in getattr(msg, "content", ())
        if getattr(block, "type", None) == "text"
    ).strip()


def _jsonable_request(request: CaseNoteClassificationRequest) -> dict:
    return {
        "tenant_id": request.tenant_id,
        "account_id": request.account_id,
        "case_id": request.case_id,
        "case_note_text": request.case_note_text,
        "allowed_case_ids": list(request.allowed_case_ids()),
        "prompt_version": SLOT_A_PROMPT_VERSION,
    }


def _trusted_note_text(text: str) -> str:
    chunks = re.split(r"(?<=[.!?\n;])\s+", text)
    trusted = [
        chunk
        for chunk in chunks
        if chunk.strip() and not any(pattern.search(chunk) for pattern in _INSTRUCTION_PATTERNS)
    ]
    return " ".join(trusted)


def _phrase_hits(text: str, phrases: tuple[str, ...]) -> tuple[str, ...]:
    normalized = " ".join(text.lower().split())
    return tuple(phrase for phrase in phrases if phrase in normalized)


def _hit_text(hits: tuple[str, ...]) -> str:
    return ", ".join(hits[:3])


def _display_prompt_path() -> str:
    repo = Path(__file__).resolve().parents[3]
    try:
        return str(SLOT_A_PROMPT_PATH.relative_to(repo))
    except ValueError:
        return str(SLOT_A_PROMPT_PATH)
