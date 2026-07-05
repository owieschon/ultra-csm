#!/bin/bash
# Ultra-CSM daily operating run.
#
# Computes today's story day from the frozen live-reseed anchor
# (anchor_date; see ~/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json
# and its anchor.py sibling -- reused arithmetic, not reimplemented: story_day
# = (today - anchor_date).days), maps it onto the same fixture-day-offset
# space tick.py/demo-sweep already use (as_of = SEED_DATE + story_day, since
# translated_date = fixture_date + (anchor_date - fixture_seed_date) implies
# fixture day_offset == story_day for "today"), runs the deterministic
# briefing/sweep surfaces as-of that day, ledgers one summary line with cost,
# and -- credentials permitting, under a hard $2 cap -- judges the day's new
# Slot B drafts via the already-built eval/judge_live_csm.py.
#
# Artifacts are written OUT OF REPO to ~/ultra-csm-operating-runs/<date>/;
# never committed (see docs/OPERATING_PROOF.md).

set -euo pipefail

REPO_ROOT="$HOME/dev/ultra-csm-operating-cadence"
ANCHOR_PATH="$HOME/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json"
RUNS_ROOT="$HOME/ultra-csm-operating-runs"
LOG_PATH="$RUNS_ROOT/operating_log.jsonl"
JUDGE_COST_CAP_USD="2.00"

cd "$REPO_ROOT"

RUN_DATE="$(date +%F)"
OUT_DIR="$RUNS_ROOT/$RUN_DATE"
mkdir -p "$OUT_DIR"

echo "============================================"
echo "Ultra-CSM daily operating run: $RUN_DATE"
echo "============================================"

# --- Story day + fixture as-of (reuses anchor.json's frozen anchor_date;
# never recomputes it, per anchor.json's own note) -----------------------
read -r STORY_DAY FIXTURE_AS_OF <<PYEOF
$(PYTHONPATH=src:. .venv/bin/python - "$ANCHOR_PATH" <<'PYSCRIPT'
import json
import sys
from datetime import date, timedelta

from ultra_csm.data_plane.synthetic_book import SEED_DATE

anchor = json.loads(open(sys.argv[1]).read())
anchor_date = date.fromisoformat(anchor["anchor_date"])
today = date.today()
story_day = (today - anchor_date).days
fixture_as_of = (date.fromisoformat(SEED_DATE) + timedelta(days=story_day)).isoformat()
print(story_day, fixture_as_of)
PYSCRIPT
)
PYEOF

echo "story_day=$STORY_DAY fixture_as_of=$FIXTURE_AS_OF"

# --- Deterministic surfaces (existing ucsm CLI; MUST NOT edit src/) ------
# tick runs LIVE (not --dry-run): only the real sweep resolves motions
# (CSMWorkItem.motion, via playbook_tenant_slug threaded in tick.py's
# non-dry-run path) and writes tick_work_queue_<stamp>.json -- the
# motion-bearing artifact this dispatch exists to capture. --state-dir
# keeps its output out-of-repo alongside everything else here.
TICK_STATE_DIR="$OUT_DIR/tick_state"
echo ""
echo "-- tick --as-of $FIXTURE_AS_OF (live sweep, motions resolved) --"
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli tick \
  --as-of "$FIXTURE_AS_OF" --state-dir "$TICK_STATE_DIR" --json \
  > "$OUT_DIR/tick.json"

STAMP="${FIXTURE_AS_OF//-/}"
if [ -f "$TICK_STATE_DIR/tick_work_queue_$STAMP.json" ]; then
  cp "$TICK_STATE_DIR/tick_work_queue_$STAMP.json" "$OUT_DIR/briefing.json"
else
  echo "FATAL: tick produced no work-queue artifact at $TICK_STATE_DIR/tick_work_queue_$STAMP.json" >&2
  exit 1
fi

echo "-- demo-sweep --day $STORY_DAY --deep (health/priority scorecard, feeds briefing inputs) --"
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-sweep \
  --day "$STORY_DAY" --deep --json \
  > "$OUT_DIR/sweep.json"

if [ ! -s "$OUT_DIR/briefing.json" ]; then
  echo "FATAL: briefing artifact is empty" >&2
  exit 1
fi

# --- Judge lane: credentialed, cost-capped, additive ---------------------
KEY_ENV="${ANTHROPIC_ENV_FILE:-$HOME/dev/parts-cs-agent/.env}"
if [ -f "$KEY_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$KEY_ENV"
  set +a
fi

JUDGE_COST_USD="0.00"
JUDGE_STATUS="skipped_no_key"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo ""
  echo "############################################"
  echo "# JUDGE LANE SKIPPED: ANTHROPIC_API_KEY not set"
  echo "# (checked \$ANTHROPIC_API_KEY and $KEY_ENV)"
  echo "############################################"
else
  echo ""
  echo "-- judge lane preflight: projecting worst-case cost against \$$JUDGE_COST_CAP_USD cap --"
  PROJECTED_COST="$(PYTHONPATH=src:. .venv/bin/python - <<'PYSCRIPT'
from ultra_csm.cost_tracker import estimate_call_cost, compute_cost
from eval.judge_live_csm import DEFAULT_SLUGS, DEFAULT_RUNS_PER_CANDIDATE

writer_cost = estimate_call_cost("claude-opus-4-8")
judge_cost = compute_cost("claude-sonnet-4-6", 2000, 700)
n = len(DEFAULT_SLUGS)
total = n * writer_cost + n * DEFAULT_RUNS_PER_CANDIDATE * judge_cost
print(f"{total:.4f}")
PYSCRIPT
)"
  echo "projected_cost_usd=$PROJECTED_COST cap_usd=$JUDGE_COST_CAP_USD"

  OVER_CAP="$(PYTHONPATH=src:. .venv/bin/python -c "print(1 if float(\"$PROJECTED_COST\") > float(\"$JUDGE_COST_CAP_USD\") else 0)")"
  if [ "$OVER_CAP" = "1" ]; then
    echo "############################################"
    echo "# JUDGE LANE ABORTED: projected cost \$$PROJECTED_COST exceeds \$$JUDGE_COST_CAP_USD cap"
    echo "# (lane aborted, not the run -- deterministic artifacts above are unaffected)"
    echo "############################################"
    JUDGE_STATUS="aborted_over_cap"
  else
    echo "-- running eval.judge_live_csm (day $STORY_DAY new Slot B drafts) --"
    # set -e is repo-wide for this script; the judge lane's own failure must
    # abort the LANE, not the run (Decisions section), so its exit status is
    # captured explicitly rather than left to trip the script-wide trap.
    set +e
    PYTHONPATH=src:. .venv/bin/python -m eval.judge_live_csm \
      --anchor "$ANCHOR_PATH" \
      --output-dir "$OUT_DIR/judge_gold" \
      > "$OUT_DIR/judge_live.log" 2>&1
    JUDGE_EXIT=$?
    set -e
    if [ "$JUDGE_EXIT" -eq 0 ]; then
      JUDGE_COST_USD="$PROJECTED_COST"
      JUDGE_STATUS="ran"
      cp "$OUT_DIR"/judge_gold/judge_live_*.json "$OUT_DIR/judge_live.json" 2>/dev/null || true
    else
      echo "############################################"
      echo "# JUDGE LANE FAILED (exit $JUDGE_EXIT) -- see $OUT_DIR/judge_live.log"
      echo "# (lane failure only, not the run -- deterministic artifacts above are unaffected)"
      echo "############################################"
      JUDGE_STATUS="failed"
    fi
  fi
fi

# --- Ledger: one summary line -------------------------------------------
ACCOUNTS_FLAGGED="$(PYTHONPATH=src:. .venv/bin/python - "$OUT_DIR/sweep.json" <<'PYSCRIPT'
import json
import sys

data = json.loads(open(sys.argv[1]).read())
dist = data.get("health_distribution", {})
print(dist.get("yellow", 0) + dist.get("red", 0))
PYSCRIPT
)"

PYTHONPATH=src:. .venv/bin/python - \
  "$LOG_PATH" "$RUN_DATE" "$STORY_DAY" "$FIXTURE_AS_OF" "$ACCOUNTS_FLAGGED" "$JUDGE_STATUS" "$JUDGE_COST_USD" <<'PYSCRIPT'
import json
import sys
from pathlib import Path

log_path, run_date, story_day, fixture_as_of, accounts_flagged, judge_status, judge_cost_usd = sys.argv[1:8]

Path(log_path).parent.mkdir(parents=True, exist_ok=True)
entry = {
    "artifact": "operating_log_entry",
    "date": run_date,
    "story_day": int(story_day),
    "fixture_as_of": fixture_as_of,
    "accounts_flagged": int(accounts_flagged),
    "judge_status": judge_status,
    "cost_usd": float(judge_cost_usd),
    "claim_boundary": {"sim": True, "live": False},
}
with open(log_path, "a") as f:
    f.write(json.dumps(entry, sort_keys=True) + "\n")
print(json.dumps(entry, indent=2, sort_keys=True))
PYSCRIPT

echo ""
echo "============================================"
echo "Run complete: $RUN_DATE (story day $STORY_DAY)"
echo "Artifacts: $OUT_DIR"
echo "Ledger: $LOG_PATH"
echo "============================================"
