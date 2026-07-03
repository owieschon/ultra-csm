from __future__ import annotations

import inspect
import json

import pytest

from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.email_drafts import (
    EmailDraftError,
    GmailDraftCommitter,
    render_email_draft_from_proposal,
)
from ultra_csm.governance import ActionProposal, canonical_payload_sha256


class FakeGmailClient:
    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if req.url == "https://oauth2.googleapis.com/token":
            return HttpResponse(
                status=200,
                body=b'{"access_token":"gmail-token"}',
                headers={"content-type": "application/json"},
            )
        if req.url == "https://gmail.googleapis.com/gmail/v1/users/me/drafts":
            return HttpResponse(
                status=200,
                body=b'{"id":"draft-123"}',
                headers={"content-type": "application/json"},
            )
        return HttpResponse(status=404, body=b"{}", headers={})


def test_render_email_draft_requires_approved_proposal_and_binds_payload_sha():
    pending = _proposal(status="pending")

    with pytest.raises(EmailDraftError, match="approved"):
        render_email_draft_from_proposal(pending)

    approved = _proposal(status="approved")
    artifact = render_email_draft_from_proposal(approved)

    assert artifact.to == "ops@example.test"
    assert artifact.subject == "Activation follow-up"
    assert artifact.payload_sha256 == approved.payload_sha256
    assert artifact.claim_boundary == {
        "draft_never_send": True,
        "live_send_performed": False,
        "approved_proposal_required": True,
    }
    assert artifact.placement["gmail_api"]["method"] == "users.drafts.create"


def test_gmail_draft_committer_creates_draft_only_and_records_receipt():
    proposal = _proposal(status="approved")
    artifact = render_email_draft_from_proposal(proposal)
    client = FakeGmailClient()
    committer = GmailDraftCommitter(
        env={
            "ULTRA_CSM_GMAIL_CLIENT_ID": "client",
            "ULTRA_CSM_GMAIL_CLIENT_SECRET": "secret",
            "ULTRA_CSM_GMAIL_REFRESH_TOKEN": "refresh",
        },
        client=client,
    )

    receipt = committer.create_draft(proposal, artifact)

    assert receipt.draft_id == "draft-123"
    assert receipt.payload_sha256 == proposal.payload_sha256
    assert receipt.claim_boundary["draft_never_send"] is True
    assert [request.method for request in client.requests] == ["POST", "POST"]
    assert client.requests[1].url.endswith("/drafts")
    assert all("/send" not in request.url for request in client.requests)
    body = json.loads(client.requests[1].body.decode("utf-8"))
    assert body["message"]["raw"]


def test_gmail_draft_committer_refuses_unapproved_or_mismatched_payload():
    approved = _proposal(status="approved")
    pending = _proposal(status="pending")
    artifact = render_email_draft_from_proposal(approved)
    committer = GmailDraftCommitter(
        env={
            "ULTRA_CSM_GMAIL_CLIENT_ID": "client",
            "ULTRA_CSM_GMAIL_CLIENT_SECRET": "secret",
            "ULTRA_CSM_GMAIL_REFRESH_TOKEN": "refresh",
        },
        client=FakeGmailClient(),
    )

    with pytest.raises(EmailDraftError, match="approved"):
        committer.create_draft(pending, artifact)

    tampered = _proposal(status="approved", subject="Different")
    with pytest.raises(EmailDraftError, match="sha"):
        committer.create_draft(tampered, artifact)


def test_gmail_committer_has_no_gmail_delivery_endpoint():
    import ultra_csm.email_drafts as email_drafts

    source = inspect.getsource(email_drafts)

    assert "messages/send" not in source
    assert "drafts/send" not in source
    assert "messages.send" not in source


def _proposal(*, status: str, subject: str = "Activation follow-up") -> ActionProposal:
    payload = {
        "account_id": "acct-001",
        "contact_email": "ops@example.test",
        "subject": subject,
        "body": "Please review the activation plan.",
    }
    return ActionProposal(
        proposal_id="proposal-001",
        intent="time_to_value",
        action="draft_customer_outreach",
        payload=payload,
        payload_sha256=canonical_payload_sha256(payload),
        autonomy_tier=2,
        required_permission="customer.outreach.draft",
        status=status,
    )
