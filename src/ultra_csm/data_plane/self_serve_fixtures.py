"""Fixture-only self-serve delivery and call-intelligence adapters."""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.data_plane.contracts import (
    CallTranscript,
    LifecycleEmailDraft,
    ProductUser,
    SalesEngagementEnrollmentDraft,
)
from ultra_csm.data_plane.fixtures import ACME_LOGISTICS, det_id


class TranscriptDomainError(ValueError):
    """Raised when a transcript is presented to a validated outreach-draft lane."""


@dataclass(frozen=True)
class FixtureLifecycleEmailConnector:
    """Loops-shaped fixture connector. It records drafts and never sends."""

    def create_draft(
        self,
        *,
        user: ProductUser,
        content_id: str,
        subject: str,
        body: str,
        idempotency_key: str,
        created_at: str,
    ) -> LifecycleEmailDraft:
        return LifecycleEmailDraft(
            draft_id=det_id("loops-draft", user.user_id, content_id, idempotency_key),
            user_id=user.user_id,
            email=user.email,
            content_id=content_id,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
            created_at=created_at,
            send_performed=False,
        )


@dataclass(frozen=True)
class FixtureSalesEngagementConnector:
    """Amplemarket-shaped fixture connector. It records enrollments only."""

    def create_enrollment_draft(
        self,
        *,
        user: ProductUser,
        sequence_id: str,
        content_id: str,
        step_metadata: tuple[tuple[str, str], ...],
        idempotency_key: str,
        created_at: str,
    ) -> SalesEngagementEnrollmentDraft:
        return SalesEngagementEnrollmentDraft(
            enrollment_id=det_id(
                "amplemarket-enrollment-draft",
                user.user_id,
                sequence_id,
                content_id,
                idempotency_key,
            ),
            user_id=user.user_id,
            email=user.email,
            sequence_id=sequence_id,
            content_id=content_id,
            step_metadata=tuple(sorted(step_metadata)),
            idempotency_key=idempotency_key,
            created_at=created_at,
            enrollment_performed=False,
        )


GONG_FIXTURE_TRANSCRIPTS: tuple[CallTranscript, ...] = (
    CallTranscript(
        transcript_id=det_id("gong-transcript", ACME_LOGISTICS, "activation-review"),
        account_id=ACME_LOGISTICS,
        external_call_id="gong-call-fixture-activation-review",
        provider="gong",
        title="Activation review",
        occurred_at="2026-06-20T15:00:00Z",
        speaker_emails=("csm@example.test", "jordan@example.test"),
        transcript_text=(
            "Fixture transcript: the customer described onboarding blockers and "
            "asked for a clearer admin setup path."
        ),
        source_ref="gong_fixture:activation_review",
    ),
    CallTranscript(
        transcript_id=det_id("gong-transcript", ACME_LOGISTICS, "workflow-training"),
        account_id=ACME_LOGISTICS,
        external_call_id="gong-call-fixture-workflow-training",
        provider="gong",
        title="Workflow training",
        occurred_at="2026-06-24T16:00:00Z",
        speaker_emails=("csm@example.test", "jordan@example.test"),
        transcript_text=(
            "Fixture transcript: the team reviewed workflow steps and confirmed "
            "that deeper automation should wait for admin completion."
        ),
        source_ref="gong_fixture:workflow_training",
    ),
)


@dataclass(frozen=True)
class FixtureCallIntelligenceConnector:
    """Gong-shaped fixture connector with no summarization or judge exposure."""

    transcripts: tuple[CallTranscript, ...] = GONG_FIXTURE_TRANSCRIPTS

    def list_transcripts(self, account_id: str) -> list[CallTranscript]:
        return [row for row in self.transcripts if row.account_id == account_id]


def assert_transcript_out_of_slot_b_domain(transcript: CallTranscript) -> None:
    """Fail closed if a call transcript is routed toward the Slot B judge.

    MP-E's transcript lane is contract-only. The validated Slot B domain is
    outreach draft quality, not raw call intelligence.
    """

    raise TranscriptDomainError(
        f"{transcript.transcript_id}: call transcripts are out_of_validated_domain for Slot B"
    )
