# Ultra CSM Observability

<!-- clean-docs:purpose -->
Status: active observability landing page.
<!-- clean-docs:end purpose -->
<!-- clean-docs:allow section-length reason="The troubleshooting branch is one symptom-to-repair decision tree" -->

Observability is a port around the proof, not an authority path. Offline evals
remain deterministic and credential-free.

The kept package exposes:

- `NoOpTracer` and `NoOpMeter` for the scored default path.
- `RecordingTracer` and `RecordingMeter` for deterministic tests and fake-client
  Slot B verification.
- Span/meter protocols that live adapters can implement later without changing
  Agent 1 logic.

Agent 1 uses observability around Slot B live calls only when a caller injects
recording or live implementations. The deterministic scorecard does not depend on
wall-clock timing, network exporters, or credentials.

## Troubleshooting
<!-- clean-docs:allow section-length reason="The Troubleshooting reference keeps its ordered evidence and constraints together" -->

Known hazards a stranger reading an error message would hit, and where each is
handled:

- **Missing pg tooling.** `initdb`/`pg_ctl` not found is reported by
  `make doctor`'s `postgres binaries` check with the exact fix inline; see
  README's Postgres 16 install lines (macOS `brew install postgresql@16`,
  Ubuntu `sudo apt-get install -y postgresql-16`) rather than duplicating them
  here.
- **The locale/postmaster hazard.** With no `LC_ALL`/`LANG` set at all, macOS
  Postgres 16 dies at startup with `FATAL: postmaster became multithreaded`
  (a CoreFoundation locale lookup failure); with `LC_ALL=C`, `initdb` creates a
  `SQL_ASCII` database that later rejects this repo's UTF-8 schema. This repo's
  own ephemeral-cluster bootstrap (`ultra_csm.platform._pg_env`) already
  self-heals this by forcing a UTF-8 locale into the subprocess environment
  when the caller's shell doesn't already have one — named here explicitly
  because a stranger hitting the raw error before that self-heal existed, or
  running a variant of this repo without it, still needs the explanation. If
  you see either error directly, the fix is `export LC_ALL=en_US.UTF-8
  LANG=en_US.UTF-8` (or any UTF-8 locale) before running `make eval`/`make
  demo`/`make doctor`.
- **Orphaned ephemeral-Postgres clusters.** An interrupted session (a killed
  process, a crashed test run) can leave a `build/tmp/pgdata.*` datadir with a
  live-looking `postmaster.pid` but no actual running postmaster behind it.
  `ultra_csm.platform.reap_stale_clusters` (invoked by both `make clean` and
  `make doctor`) scans for exactly this: a `pgdata.*` directory whose recorded
  postmaster PID is confirmed NOT alive. It only ever reaps a directory that
  meets both conditions — a live postmaster PID (an in-use cluster, possibly
  from a concurrent run) is never touched. Run `make doctor` to see what, if
  anything, it finds and reaps.
- **The tokenless-API default.** `make serve` binds `127.0.0.1` by default
  (see the `HOST` Makefile variable; pass `HOST=0.0.0.0` explicitly for LAN
  access). Separately, `ULTRA_CSM_DEMO_NOAUTH=1` allows tokenless local demo
  approvals through the API/MCP verdict tools — it logs an explicit warning
  when enabled and is meant for local demo use only, never a deployed
  instance.
- **Missing connector credentials.** Live data-plane connectors (Salesforce,
  Attio, Gainsight, Rocketlane, etc.) read per-source credential env vars —
  see `.env.example` for the full list and `connector_catalog.py` for the
  exact variables per connector. The offline eval needs none of these at all
  (it runs entirely on fixtures against a native ephemeral Postgres with
  trust auth). A live connector run with credentials missing fails closed
  with a typed, explicit error naming the missing variable (see
  `data_plane/readiness.py`'s `validate_readiness_state`) rather than a
  silent fallback or a generic stack trace.
