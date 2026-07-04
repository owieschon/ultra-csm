"""Support-case verbatims for the four technical cases in the bible's
error-string canon table (Pinehill's three integration cases, Ironridge's
one webhook case).

Keyed by the case's real ``det_id`` (computed the same way
``data_simulator.py`` computes ``case_id = det_id("case", account_id,
f"deep-d{open_day}-{topic}")`` for these rows -- verified by direct
comparison against ``pinehill_cases_as_of``/``cases_as_of`` output, not
guessed), so a future consumer can join this content onto the existing
``CRMCase`` rows by id without any new field on the frozen ``CRMCase``
contract (see docs/PROGRAM_REPORT_6.md's precedent for declining to widen a
contract for a secondary need).

This data is dormant: nothing in the product reads it yet. It is corpus
for a future live-seeding program (Rocketlane/Salesforce case bodies and
comment threads), authored now so that program has real content instead of
starting from a blank page. Every error string below matches
docs/SYNTHETIC_UNIVERSE_BIBLE.md's error-string canon table verbatim --
Phase E's cross-channel battery checks this.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.data_plane.canary_registry import TENANT, canary_token
from ultra_csm.data_plane.fixtures import account_id_for, det_id


@dataclass(frozen=True)
class CaseComment:
    author: str
    body: str


@dataclass(frozen=True)
class CaseVerbatim:
    case_id: str
    body: str
    comments: tuple[CaseComment, ...]


_PINEHILL = account_id_for("pinehill-transport")
_IRONRIDGE = account_id_for("ironridge-fleet")


def _case_id(account_id: str, open_day: int, topic: str = "integration") -> str:
    return det_id("case", account_id, f"deep-d{open_day}-{topic}")


VERBATIMS: dict[str, CaseVerbatim] = {
    _case_id(_PINEHILL, 0): CaseVerbatim(
        case_id=_case_id(_PINEHILL, 0),
        body=(
            "Dispatch Bridge is failing to connect to our RouteLedger 5.2 system during initial "
            "setup. Getting a connection refused error on every attempt. Our IT contact (Raul) "
            "has the service account credentials ready but the handshake never completes."
        ),
        comments=(
            CaseComment(
                author="Ben Alvarez (FleetOps Support)",
                body=(
                    "Pulled the connector logs: DISPATCH_BRIDGE_CONNECT_FAILURE: RouteLedger 5.2 "
                    "SOAP endpoint refused connection (fault code AUTH-401, host "
                    "dispatch.pinehill-transport.internal:8443). AUTH-401 usually means the "
                    "service account exists but lacks the SOAP endpoint role. Looping in Grace "
                    "Okafor from our integration team."
                ),
            ),
            CaseComment(
                author="Raul (Pinehill IT contractor)",
                body="Checking the account's role assignment on our end now, will update.",
            ),
            CaseComment(
                author="Grace Okafor (FleetOps Integration)",
                body=(
                    "Confirmed with Raul: the service account's SOAP endpoint permission was "
                    "disabled by default on RouteLedger's role template. Re-enabled and retested "
                    "the handshake successfully."
                ),
            ),
            CaseComment(
                author="Internal Note",
                body=f"Internal reference: {canary_token(TENANT, 'pinehill-transport')}",
            ),
        ),
    ),
    _case_id(_PINEHILL, 30): CaseVerbatim(
        case_id=_case_id(_PINEHILL, 30),
        body=(
            "Even after the AUTH-401 fix, we're now seeing the Dispatch Bridge connection time "
            "out intermittently -- several dispatch jobs per day are failing to complete."
        ),
        comments=(
            CaseComment(
                author="Ben Alvarez (FleetOps Support)",
                body=(
                    "Logs show: DISPATCH_BRIDGE_TIMEOUT: upstream RouteLedger socket closed after "
                    "30000ms (job batch 4417, retry_count=3). This looks like RouteLedger's own "
                    "socket timeout is shorter than our default retry window."
                ),
            ),
            CaseComment(
                author="Grace Okafor (FleetOps Integration)",
                body=(
                    "Recommending we shorten our retry-timeout setting to match RouteLedger's "
                    "socket limit rather than asking Pinehill to change their system config. "
                    "Scheduling a joint working session with Raul to apply and verify the fix."
                ),
            ),
            CaseComment(
                author="Internal Note",
                body=f"Internal reference: {canary_token(TENANT, 'pinehill-transport')}",
            ),
        ),
    ),
    _case_id(_PINEHILL, 80): CaseVerbatim(
        case_id=_case_id(_PINEHILL, 80),
        body=(
            "The Dispatch Bridge connector is still dropping events even after the retry-timeout "
            "change -- this is worse than the timeout issue, we're missing dispatch events "
            "entirely now, not just seeing delays."
        ),
        comments=(
            CaseComment(
                author="Ben Alvarez (FleetOps Support)",
                body=(
                    "Confirmed via the acknowledgement logs: DISPATCH_BRIDGE_EVENT_LOSS: 214 of "
                    "1,880 dispatch events unacknowledged in trailing 24h window (RouteLedger ack "
                    "timeout, queue=pinehill-dispatch-out). That's about 11% event loss, escalating "
                    "to a senior engineer alongside Grace."
                ),
            ),
            CaseComment(
                author="Grace Okafor (FleetOps Integration)",
                body=(
                    "Root cause: the retry-timeout fix reduced client-side timeouts but didn't "
                    "address RouteLedger's own acknowledgement queue backing up under load. Working "
                    "with Pinehill's second contractor (who built the original RouteLedger "
                    "integration) on a queue-depth fix."
                ),
            ),
            CaseComment(
                author="Internal Note",
                body=f"Internal reference: {canary_token(TENANT, 'pinehill-transport')}",
            ),
        ),
    ),
    _case_id(_IRONRIDGE, 40): CaseVerbatim(
        case_id=_case_id(_IRONRIDGE, 40),
        body=(
            "Our maintenance-ticketing system is intermittently not receiving the Maintenance "
            "Radar alert webhooks we set up -- a handful of alerts over the last hour and a half "
            "never arrived."
        ),
        comments=(
            CaseComment(
                author="Ben Alvarez (FleetOps Support)",
                body=(
                    "Confirmed: WEBHOOK_DELIVERY_500: outbound maintenance-alert webhook to "
                    "Ironridge's ticketing endpoint returned HTTP 500 on 6 of 140 attempts over 90 "
                    "minutes (endpoint https://tickets.ironridge-fleet.example/hooks/fleetops, no "
                    "retry backoff configured). This was a transient issue on the receiving "
                    "endpoint's side, not ours -- adding retry backoff on our outbound side as a "
                    "safeguard regardless."
                ),
            ),
            CaseComment(
                author="Ben Alvarez (FleetOps Support)",
                body=(
                    "Retested delivery over the following two days -- zero failures. Closing as "
                    "resolved; this was a same-week transient glitch, not a recurring pattern."
                ),
            ),
            CaseComment(
                author="Internal Note",
                body=f"Internal reference: {canary_token(TENANT, 'ironridge-fleet')}",
            ),
        ),
    ),
}
