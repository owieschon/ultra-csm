"""Loopway support-chat fixtures (Universe v2, WS-Tenant-Loopway, Wave 3).

Loopway's support surface is Intercom-ish in-app chat, not email --
``docs/TENANT_LOOPWAY_BIBLE.md``'s "Chat class" section. Twelve accounts
get short chat transcripts:

- 4 of Arc L1's 35 stalled accounts, asking setup questions during the
  day-30-45 signup wave -- corroborating evidence for the L1 cohort
  action (their chat evidence ids are expected to appear among the
  cohort_action's cited evidence -- see ``eval/loopway_battery.py``'s
  chat-signal integration check).
- 8 ordinary plain-tail accounts with routine, thin, benign chat
  (billing/feature questions) -- proving chat fixtures don't manufacture
  false signal on accounts with no story.

Produces ``CommunicationSignal``-compatible rows tagged
``channel="chat"`` via the additive Literal widening recorded in
``contracts.py`` and the bible.
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import CommunicationSignal
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.tenants.loopway.synthetic_book import L1_STALLED, PLAIN_TAIL_SAMPLE_40

SEED_CLOCK_CHAT = "2026-06-21T00:00:00Z"

# 4 of L1's 35 stalled accounts -- the first 4 by list order (deterministic,
# not random), asking setup questions during the signup wave.
L1_CHAT_ACCOUNTS: tuple[str, ...] = L1_STALLED[:4]

# 8 ordinary plain-tail accounts with routine, boring chat -- drawn from the
# fixed 40-account tail sample so this fixture never needs an account
# outside the battery's own sampling scope.
PLAIN_CHAT_ACCOUNTS: tuple[str, ...] = PLAIN_TAIL_SAMPLE_40[:8]

CHAT_ACCOUNTS: tuple[str, ...] = L1_CHAT_ACCOUNTS + PLAIN_CHAT_ACCOUNTS
assert len(CHAT_ACCOUNTS) == 12

# (day_offset, question_text, response_time_hours)
_L1_SETUP_QUESTIONS: tuple[tuple[int, str, float], ...] = (
    (32, "Hi -- I signed up last week but I can't figure out how to get a driver into the app. Where do I invite them?", 4.5),
    (33, "Following up -- still stuck on driver invites, is there a doc for this?", 12.0),
)

_PLAIN_QUESTIONS: dict[str, tuple[int, str, float]] = {}


def _plain_question_for(slug: str, idx: int) -> tuple[int, str, float]:
    topics = [
        ("Quick question -- does the Starter plan include proof-of-delivery, or is that an add-on?", 2.0),
        ("How do I add a second driver to my account?", 1.5),
        ("Is there a way to export my route history to CSV?", 3.0),
        ("Just checking -- is the analytics dashboard included at my plan tier?", 2.5),
        ("Can I change my billing email?", 1.0),
        ("Do you support multi-stop optimization on the free trial?", 2.0),
        ("How long does proof-of-delivery photo storage last?", 4.0),
        ("Is there a mobile app for iOS and Android both?", 1.5),
    ]
    day_offset = 40 + idx * 5
    text, rt = topics[idx % len(topics)]
    return (day_offset, text, rt)


def chat_signals_as_of(account_id: str, as_of_day: int, *, slug: str) -> tuple[CommunicationSignal, ...]:
    """CommunicationSignal rows (channel="chat") visible as of *as_of_day*
    for *slug* -- empty tuple for any account outside ``CHAT_ACCOUNTS`` or
    with no message yet due by this day (no fabricated early visibility)."""

    if slug in L1_CHAT_ACCOUNTS:
        rows = _L1_SETUP_QUESTIONS
    elif slug in PLAIN_CHAT_ACCOUNTS:
        idx = PLAIN_CHAT_ACCOUNTS.index(slug)
        rows = (_plain_question_for(slug, idx),)
    else:
        return ()

    signals = []
    for day_offset, _text, response_time_hours in rows:
        if day_offset > as_of_day:
            continue
        signals.append(
            CommunicationSignal(
                signal_id=det_id("signal", account_id, "chat", day_offset),
                account_id=account_id,
                contact_id=det_id("contact", account_id, f"admin@{slug.replace('-', '')}.example"),
                channel="chat",
                direction="inbound",
                timestamp=SEED_CLOCK_CHAT,
                response_time_hours=response_time_hours,
            )
        )
    return tuple(signals)


def all_chat_signals_as_of(as_of_day: int) -> dict[str, tuple[CommunicationSignal, ...]]:
    """Chat signals for every account in ``CHAT_ACCOUNTS``, keyed by
    account_id -- the shape a cohort-action evidence check consumes."""

    return {
        account_id_for(slug): chat_signals_as_of(account_id_for(slug), as_of_day, slug=slug)
        for slug in CHAT_ACCOUNTS
    }
