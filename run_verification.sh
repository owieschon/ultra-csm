#!/bin/bash
# Ultra-CSM full verification suite.

set -euo pipefail
LOGFILE="$HOME/dev/ultra-csm/verification_output.log"
exec > >(tee "$LOGFILE") 2>&1

echo "============================================"
echo "Ultra-CSM Verification Suite"
echo "Started: $(date)"
echo "============================================"

cd "$HOME/dev/ultra-csm"

echo ""
echo "============================================"
echo "1. make eval (pytest)"
echo "============================================"
make eval

echo ""
echo "============================================"
echo "2. make scorecard-csm"
echo "============================================"
make scorecard-csm

echo ""
echo "============================================"
echo "3. make regression-csm"
echo "============================================"
make regression-csm

echo ""
echo "============================================"
echo "4. make lint"
echo "============================================"
make lint

echo ""
echo "============================================"
echo "5. make hygiene"
echo "============================================"
make hygiene

if [ "${RUN_JUDGE_GATE:-0}" = "1" ]; then
  KEY_ENV="${ANTHROPIC_ENV_FILE:-$HOME/dev/parts-cs-agent/.env}"
  if [ -f "$KEY_ENV" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$KEY_ENV"
    set +a
  fi

  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ANTHROPIC_API_KEY is required when RUN_JUDGE_GATE=1."
    echo "Set it in the environment or set ANTHROPIC_ENV_FILE to a local env file."
    exit 2
  fi

  echo ""
  echo "============================================"
  echo "6. make judge-agreement-csm"
  echo "============================================"
  make judge-agreement-csm
else
  echo ""
  echo "============================================"
  echo "6. judge gate skipped"
  echo "============================================"
  echo "Set RUN_JUDGE_GATE=1 to include the credentialed judge lane."
fi

echo ""
echo "============================================"
echo "Verification complete: $(date)"
echo "============================================"
echo "Log saved to: $LOGFILE"
