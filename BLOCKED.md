# BLOCKED — Harvest 8: Act 2 — Gmail write-back (Wave D)

Dispatch: `/Users/owieschon/ultra-csm-dispatches/harvest/08_ACT2_GMAIL_WRITEBACK.md`
Worktree: `~/dev/ultra-csm-act2-gmail-writeback`, branch `codex/act2-gmail-writeback`
Blocked at: Phase 0 (Preconditions), before any code was written for the
committer itself.

(Note: `BLOCKED.md` was already a tracked file on `main` at HEAD (commit
8a86806, PR #32) — content from an earlier, unrelated Report 25/Act 1 STOP
that was evidently committed as part of that PR's history. That block was
for a missing `ANTHROPIC_API_KEY` and is unrelated to this dispatch;
Report 25/PR #32 itself is confirmed merged on origin/main, so that
episode is resolved. Per K8 convention this dispatch reuses the same
`BLOCKED.md` path for its own STOP state, overwriting the stale content
below.)

## STOP condition hit (verbatim from the dispatch)

Preconditions section: "Gmail API send scope actually authorized: a
scope/token check that does NOT send (e.g. fetch the account's profile via
the API) -> 200. Scope missing = STOP (credential changes are owner-only)."

Also listed under "## STOP conditions": "Send scope not authorized on the
burner account (credential/scope changes are owner-only)."

## What was checked and what it showed

1. Confirmed `~/ultra-csm-live-creds.env` exists and carries Gmail-related
   vars by name/count only (9 matches for `GMAIL|GOOGLE`):
   `ULTRA_CSM_GMAIL_CLIENT_ID`, `ULTRA_CSM_GMAIL_CLIENT_SECRET`,
   `ULTRA_CSM_GMAIL_REFRESH_TOKEN`, `ULTRA_CSM_GMAIL_SENDER`,
   `ULTRA_CSM_GMAIL_APP_PASSWORD`, `ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID`,
   `ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET`,
   `ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN`, `ULTRA_CSM_GMAIL_OAUTH_ACCOUNT`.
   Only one distinct burner account identity is present by name (no second
   recipient identity), so self-addressed send would have been the
   fallback per the dispatch's own precondition text — moot given the
   scope block below.

2. Performed the dispatch's own prescribed non-sending scope check:
   exchanged the OAuth refresh token for an access token (standard OAuth2
   token endpoint, `https://oauth2.googleapis.com/token`), then called
   Google's `tokeninfo` introspection endpoint (`https://oauth2.
   googleapis.com/tokeninfo?access_token=...`) — pure introspection, does
   not call any Gmail or Calendar API method, sends nothing. Script:
   `scripts/operating/_scope_check.py` in this worktree (reads creds by
   name only from `~/ultra-csm-live-creds.env`, never logs values; deleted
   its one scratch temp file after use).

   Result:
   - Token exchange: OK.
   - `tokeninfo` HTTP status: **200**.
   - Scopes granted: `calendar.events`, `gmail.insert`, `gmail.readonly`.
   - `gmail.send` scope present: **False**. (Checked both the specific
     `gmail.send` scope and the broad `https://mail.google.com/` scope —
     neither is present.)

3. Cross-checked against the original OAuth setup script that minted this
   token: `~/ultra-csm-corpus-runs/gmail-calendar-oauth-setup/
   setup_gmail_calendar_oauth.py`. Its own docstring is explicit and
   consistent with the empirical result: "Scopes requested: gmail.insert
   (import backdated messages into the mailbox without sending them),
   gmail.readonly (read them back live), and calendar.events (create +
   read events). Nothing here can send outbound email or modify anyone
   else's calendar." This was a deliberate, documented design choice from
   Program 9 — the burner's live-seeding tooling (IMAP APPEND via a
   separate app-password credential, used for backdated message creation)
   was built specifically to avoid ever needing send capability.

4. The only other Gmail credential present is
   `ULTRA_CSM_GMAIL_APP_PASSWORD` / `ULTRA_CSM_GMAIL_SENDER`, used
   exclusively for IMAP (both APPEND for seeding and readonly IMAP for
   `live_gmail_reader.py`, per `src/ultra_csm/data_plane/
   live_gmail_reader.py`'s own docstring: "Read-only: this module only
   ever opens the mailbox with readonly=True"). IMAP APPEND is not
   equivalent to a "send" — it creates a message directly in a mailbox
   without it ever transiting SMTP/relay, which is why Program 9 chose it
   specifically for backdated, non-deliverable seeding. Using it (or SMTP
   with this app password) to send this dispatch's live message would not
   be reusing an authorized send capability — it would be routing around
   the absence of one, which K7 and this dispatch's STOP conditions both
   name as never permitted: "a permission/scope denial is a decision, not
   an obstacle — never route around it."

## Why this stops here rather than proceeding

- The dispatch's own gate for this precondition is unambiguous: scope
  missing = STOP, and credential/scope changes are owner-only.
- The task instructions given for this run are equally explicit: if a
  needed credential/scope is not present, STOP per K8 and do not go
  looking for a workaround in other files, keychains, or other repos, and
  do not attempt to route around a missing scope even if some other
  transport path could technically move a message.
- No committer code, no send-manifest, and no live sends were built or
  attempted. Nothing was sent. The worktree contains only this BLOCKED.md,
  PROGRESS.md (excluded from git per the shared `.git/info/exclude`), and
  the read-only scope-check script, which itself performed zero Gmail or
  Calendar API calls (only OAuth token-endpoint and tokeninfo-endpoint
  calls, both introspection-only).

## What the owner needs to do to unblock

Mint (or re-mint) an OAuth token for the burner account
(`ULTRA_CSM_GMAIL_OAUTH_ACCOUNT`) that includes the `gmail.send` scope
(minimally `https://www.googleapis.com/auth/gmail.send`; the existing
`gmail.insert` + `gmail.readonly` + `calendar.events` scopes can stay
alongside it), and write the refreshed
`ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN` (and same client id/secret unless
rotated) into `~/ultra-csm-live-creds.env`.

Once `gmail.send` (or equivalent) is confirmed present via the same
non-sending `tokeninfo` check, this dispatch can resume from Phase 0 with
the scope precondition satisfied — the committer build, allowlist guard,
manifest, and mailbox-observation work in Phases 1-4 are otherwise ready
to start (sim committer pattern at `src/ultra_csm/committers.py`,
ActionGate at `src/ultra_csm/governance/gate.py`, Program 9's ledger/tag
conventions and `anchor.json` at
`~/ultra-csm-corpus-runs/live-reseed-20260704/` were all located and are
reusable, as documented in PROGRESS.md).

## Tree state

Clean. No commits made in this worktree beyond what is captured here (no
code beyond the read-only scope-check script and the two process files,
neither committed). Nothing sent, nothing mutated on the Gmail side beyond
one OAuth token refresh + one tokeninfo introspection call (both
read-only, no Gmail/Calendar API method invoked). No PR opened — nothing
passes any phase gate, so per K8 this stops at BLOCKED.md.
