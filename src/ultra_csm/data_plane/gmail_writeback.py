"""Live, burner-to-burner Gmail send committer for approved
``draft_customer_outreach`` proposals.

Mirrors :class:`~ultra_csm.data_plane.salesforce_writeback.LiveSalesforceActivityCommitter`'s
contract (the ``Committer`` protocol, the same idempotency-key derivation,
the same payload-binding check before executing, a ledger outside the repo)
but sends one Gmail message via the Gmail API ``users.messages.send``
instead of creating a Salesforce Task. Scope is deliberately narrow and
carries two guards Salesforce write-back does not need, because email adds
a recipient dimension:

* Recipient allowlist is a HARD-CODED constant, checked fail-closed at send
  time regardless of what the gate approved. A recipient outside it is
  refused with a ledger line -- never sent. The gate approving a proposal
  does not widen the transport's authority (defense in depth).
* Byte-equal body check: the subject/body actually sent must hash-identical
  match the approved proposal payload's subject/body -- never regenerated,
  never re-templated at send time.

One POST per approved proposal (``users.messages.send``, base64url-encoded
RFC 2822 raw message). Never a second call for the same idempotency key --
the ledger is checked before every send attempt. HARD SEND CAP is enforced
by the caller (the manifest script), not this module, but this module will
never send more than one message per ``commit()`` call regardless.
"""

from __future__ import annotations

import base64
import email.utils
import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from ultra_csm.committers import CommitError, CommitReceipt
from ultra_csm.data_plane.live_smoke import HttpClient, HttpRequest, UrllibHttpClient
from ultra_csm.governance import ActionGate, ActionProposal, GateOutcome, canonical_payload_sha256

# Hard-coded allowlist: the ONLY legal recipients for a live send from this
# committer. Burner-to-burner only. A recipient outside this set is refused
# even if the gate approved it -- checked at send time, every time.
RECIPIENT_ALLOWLIST = frozenset({"agenticardvarkpug@gmail.com"})

UCSM_SUBJECT_TAG = "UCSM-NARR2"

_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailWriteError(RuntimeError):
    """A live Gmail send attempt failed."""


class RecipientNotAllowedError(CommitError):
    """A proposal's recipient is outside the hard-coded burner allowlist."""


class BodyMismatchError(CommitError):
    """The subject/body about to be sent does not byte-match the approved payload."""


def _env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise GmailWriteError(f"missing required credential env var: {key}")
    return value


def gmail_access_token_from_env(env: Mapping[str, str], *, client: HttpClient | None = None) -> str:
    """Exchange the OAuth refresh token for a short-lived access token."""
    http = client or UrllibHttpClient()
    from urllib import parse

    body = parse.urlencode(
        {
            "client_id": _env(env, "ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID"),
            "client_secret": _env(env, "ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET"),
            "refresh_token": _env(env, "ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    response = http.send(
        HttpRequest(
            "POST",
            _TOKEN_URL,
            {"content-type": "application/x-www-form-urlencoded"},
            body=body,
        )
    )
    if response.status != 200:
        raise GmailWriteError(f"oauth_refresh unexpected status {response.status}")
    raw = response.json()
    if not isinstance(raw, dict) or not isinstance(raw.get("access_token"), str):
        raise GmailWriteError("oauth_refresh missing access_token")
    return raw["access_token"]


class LiveGmailOutboundCommitter:
    """Create-only live sibling of ``SimOutboundCommitter``: sends one Gmail
    message per approved ``draft_customer_outreach`` proposal, ledgered
    outside the repo, refusing any recipient outside ``RECIPIENT_ALLOWLIST``
    and any body that does not byte-match the approved payload."""

    def __init__(
        self,
        gate: ActionGate,
        *,
        env: Mapping[str, str],
        ledger_dir: Path | str,
        sender: str,
        client: HttpClient | None = None,
        subject_tag: str = UCSM_SUBJECT_TAG,
        allowlist: frozenset[str] = RECIPIENT_ALLOWLIST,
    ) -> None:
        self._gate = gate
        self._env = env
        self._client = client or UrllibHttpClient()
        self._ledger_dir = Path(ledger_dir)
        self._ledger_path = self._ledger_dir / "gmail_writeback_ledger.jsonl"
        self._sender = sender
        self._subject_tag = subject_tag
        self._allowlist = allowlist

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        recipient: str,
        dry_run: bool = False,
    ) -> CommitReceipt:
        if proposal.action != "draft_customer_outreach":
            raise CommitError(f"LiveGmailOutboundCommitter cannot commit {proposal.action}")

        # Fail-closed recipient check FIRST, before any other work, and
        # regardless of gate authorization -- the gate approving a payload
        # never widens what this transport is allowed to address.
        if recipient not in self._allowlist:
            key = _idempotency_key(proposal, outcome, target="gmail:refused")
            receipt = CommitReceipt(
                receipt_id=canonical_payload_sha256(
                    {"proposal_id": proposal.proposal_id, "idempotency_key": key, "target": "gmail:refused"}
                )[:24],
                proposal_id=proposal.proposal_id,
                action=proposal.action,
                account_id=str(proposal.payload.get("account_id") or ""),
                idempotency_key=key,
                committed=False,
                dry_run=dry_run,
                target="gmail:refused_recipient_not_allowlisted",
                payload_sha256=outcome.payload_sha256,
            )
            self._append_ledger(receipt, recipient=recipient, message_id=None, subject=None, refusal_reason="RECIPIENT_NOT_ALLOWLISTED")
            raise RecipientNotAllowedError(
                f"recipient {recipient!r} is not in the hard-coded allowlist; refusing to send"
            )

        # Approved-state + anti-TOCTOU check: reads gate state, never trusted
        # from a queue file. Raises GateError if not authorized or if the
        # payload was mutated after approval.
        self._gate.assert_payload_bound(outcome, proposal.payload)

        subject_raw = str(proposal.payload.get("subject") or "")
        body_raw = str(proposal.payload.get("body") or "")
        # Byte-equal check: what we are about to send must match the exact
        # subject/body the gate authorized -- never regenerated here.
        approved_subject = str(outcome.payload.get("subject") or "")
        approved_body = str(outcome.payload.get("body") or "")
        if subject_raw != approved_subject or body_raw != approved_body:
            raise BodyMismatchError(
                "subject/body about to be sent do not byte-match the approved payload"
            )

        key = _idempotency_key(proposal, outcome, target="gmail:send")
        already = (
            self._gate.idempotency_key_exists(key)
            if dry_run
            else not self._gate.claim_idempotency_key(
                key,
                request_id=proposal.proposal_id,
                result_ref="gmail:send:intent",
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        )
        subject = f"[{self._subject_tag}] {subject_raw}"
        receipt = CommitReceipt(
            receipt_id=canonical_payload_sha256(
                {"proposal_id": proposal.proposal_id, "idempotency_key": key, "target": "gmail:send"}
            )[:24],
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            account_id=str(proposal.payload.get("account_id") or ""),
            idempotency_key=key,
            committed=not already,
            dry_run=dry_run,
            target="gmail:send",
            payload_sha256=outcome.payload_sha256,
        )
        if dry_run or already:
            self._append_ledger(receipt, recipient=recipient, message_id=None, subject=subject, refusal_reason=None)
            return receipt

        try:
            message_id = self._send(recipient=recipient, subject=subject, body=approved_body)
        except GmailWriteError:
            self._gate.release_idempotency_key(key)
            raise
        self._gate.mark_idempotency_result(key, result_ref=f"gmail:message:{message_id}")
        self._append_ledger(receipt, recipient=recipient, message_id=message_id, subject=subject, refusal_reason=None)
        return receipt

    def _send(self, *, recipient: str, subject: str, body: str) -> str:
        access_token = gmail_access_token_from_env(self._env, client=self._client)
        raw_message = _build_rfc2822(sender=self._sender, recipient=recipient, subject=subject, body=body)
        encoded = base64.urlsafe_b64encode(raw_message).decode("ascii")
        response = self._client.send(
            HttpRequest(
                "POST",
                _GMAIL_SEND_URL,
                {
                    "authorization": f"Bearer {access_token}",
                    "content-type": "application/json",
                },
                body=json.dumps({"raw": encoded}).encode("utf-8"),
            )
        )
        if response.status not in (200, 201):
            raise GmailWriteError(f"messages.send failed: status {response.status}")
        result = response.json()
        message_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise GmailWriteError("messages.send response missing id")
        return message_id

    def _append_ledger(
        self,
        receipt: CommitReceipt,
        *,
        recipient: str,
        message_id: str | None,
        subject: str | None,
        refusal_reason: str | None,
    ) -> None:
        self._ledger_dir.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "receipt": asdict(receipt),
                        "recipient": recipient,
                        "message_id": message_id,
                        "subject": subject,
                        "refusal_reason": refusal_reason,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _build_rfc2822(*, sender: str, recipient: str, subject: str, body: str) -> bytes:
    lines = [
        f"From: {sender}",
        f"To: {recipient}",
        f"Subject: {subject}",
        f"Date: {email.utils.formatdate(localtime=True)}",
        "Content-Type: text/plain; charset=utf-8",
        "MIME-Version: 1.0",
        "",
        body,
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")


def _idempotency_key(
    proposal: ActionProposal,
    outcome: GateOutcome,
    *,
    target: str = "gmail:send",
) -> str:
    return canonical_payload_sha256({
        "proposal_id": proposal.proposal_id,
        "payload_sha256": outcome.payload_sha256,
        "target": target,
    })


def ledger_send_count(path: Path | str) -> int:
    """Count LIVE (committed, non-dry-run, non-refused) sends recorded in the
    ledger -- the authoritative counter for the hard send cap."""
    path = Path(path)
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        receipt = entry["receipt"]
        if receipt["committed"] and not receipt["dry_run"] and entry.get("message_id"):
            count += 1
    return count
