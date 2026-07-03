"""Draft-never-send email placement contracts and Gmail draft creation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from email.message import EmailMessage
import base64
from typing import Any, Mapping
from urllib import parse

from ultra_csm.data_plane.live_smoke import HttpClient, HttpRequest, UrllibHttpClient
from ultra_csm.governance import ActionProposal, canonical_payload_sha256


class EmailDraftError(RuntimeError):
    """A draft placement precondition failed."""


@dataclass(frozen=True)
class EmailDraftArtifact:
    proposal_id: str
    to: str
    subject: str
    body: str
    payload_sha256: str
    claim_boundary: dict[str, Any]
    placement: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GmailDraftReceipt:
    draft_id: str
    proposal_id: str
    payload_sha256: str
    claim_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_email_draft_from_proposal(
    proposal: ActionProposal,
    *,
    approved_payload_sha256: str | None = None,
) -> EmailDraftArtifact:
    return render_email_draft_from_payload(
        proposal_id=proposal.proposal_id,
        action=proposal.action,
        status=proposal.status,
        payload=proposal.payload,
        payload_sha256=proposal.payload_sha256,
        approved_payload_sha256=approved_payload_sha256,
    )


def render_email_draft_from_payload(
    *,
    proposal_id: str,
    action: str,
    status: str,
    payload: Mapping[str, Any],
    payload_sha256: str,
    approved_payload_sha256: str | None = None,
) -> EmailDraftArtifact:
    if action != "draft_customer_outreach":
        raise EmailDraftError(f"render_email_draft requires draft_customer_outreach, got {action}")
    if status != "approved":
        raise EmailDraftError("render_email_draft requires an approved proposal")
    actual_sha = canonical_payload_sha256(dict(payload))
    if payload_sha256 != actual_sha:
        raise EmailDraftError("proposal payload_sha256 does not match payload")
    if approved_payload_sha256 is not None and approved_payload_sha256 != actual_sha:
        raise EmailDraftError("approved payload sha does not match proposal payload")
    to = _required_text(payload, ("contact_email", "to", "email"))
    subject = _required_text(payload, ("subject",))
    body = _required_text(payload, ("body",))
    return EmailDraftArtifact(
        proposal_id=proposal_id,
        to=to,
        subject=subject,
        body=body,
        payload_sha256=actual_sha,
        claim_boundary={
            "draft_never_send": True,
            "live_send_performed": False,
            "approved_proposal_required": True,
        },
        placement={
            "kind": "email_draft",
            "host_instruction": (
                "Create a draft in the user's own email tool using exactly this "
                "to/subject/body and payload_sha256; do not deliver it."
            ),
            "gmail_api": {
                "method": "users.drafts.create",
                "required_scope": "https://www.googleapis.com/auth/gmail.compose",
            },
        },
    )


class GmailDraftCommitter:
    """Create Gmail drafts for already-approved draft artifacts."""

    def __init__(
        self,
        *,
        env: Mapping[str, str],
        client: HttpClient | None = None,
    ) -> None:
        self._env = env
        self._http = client or UrllibHttpClient()

    def create_draft(
        self,
        proposal: ActionProposal,
        artifact: EmailDraftArtifact,
    ) -> GmailDraftReceipt:
        if proposal.status != "approved":
            raise EmailDraftError("Gmail draft creation requires an approved proposal")
        if artifact.payload_sha256 != proposal.payload_sha256:
            raise EmailDraftError("draft artifact sha does not match approved proposal")
        if canonical_payload_sha256(proposal.payload) != proposal.payload_sha256:
            raise EmailDraftError("approved proposal payload hash is stale")
        token = self._access_token()
        user_id = self._env.get("ULTRA_CSM_GMAIL_USER_ID", "me")
        response = self._request(
            HttpRequest(
                "POST",
                f"https://gmail.googleapis.com/gmail/v1/users/{parse.quote(user_id)}/drafts",
                {
                    "accept": "application/json",
                    "authorization": f"Bearer {token}",
                    "content-type": "application/json",
                },
                body=_json_body({
                    "message": {
                        "raw": _rfc822_raw(artifact),
                    }
                }),
            )
        )
        if response.status not in (200, 201):
            raise EmailDraftError(f"Gmail drafts.create unexpected status {response.status}")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise EmailDraftError("Gmail drafts.create response missing draft id")
        return GmailDraftReceipt(
            draft_id=payload["id"],
            proposal_id=proposal.proposal_id,
            payload_sha256=artifact.payload_sha256,
            claim_boundary={
                "draft_never_send": True,
                "live_send_performed": False,
                "gmail_scope": "gmail.compose",
            },
        )

    def _access_token(self) -> str:
        response = self._request(
            HttpRequest(
                "POST",
                self._env.get("ULTRA_CSM_GMAIL_TOKEN_URL", "https://oauth2.googleapis.com/token"),
                {"content-type": "application/x-www-form-urlencoded"},
                body=parse.urlencode({
                    "grant_type": "refresh_token",
                    "client_id": _env(self._env, "ULTRA_CSM_GMAIL_CLIENT_ID"),
                    "client_secret": _env(self._env, "ULTRA_CSM_GMAIL_CLIENT_SECRET"),
                    "refresh_token": _env(self._env, "ULTRA_CSM_GMAIL_REFRESH_TOKEN"),
                }).encode("utf-8"),
            )
        )
        if response.status != 200:
            raise EmailDraftError(f"Gmail token refresh unexpected status {response.status}")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
            raise EmailDraftError("Gmail token refresh missing access_token")
        return payload["access_token"]

    def _request(self, req: HttpRequest):
        return getattr(self._http, "send")(req)


def _required_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise EmailDraftError(f"email draft payload missing required field: {keys[0]}")


def _rfc822_raw(artifact: EmailDraftArtifact) -> str:
    message = EmailMessage()
    message["To"] = artifact.to
    message["Subject"] = artifact.subject
    message.set_content(artifact.body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return raw.rstrip("=")


def _json_body(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        raise EmailDraftError(f"missing {key}")
    return value
