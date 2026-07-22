from pathlib import Path

import pytest

WORKFLOW = Path(".github/workflows/ci.yml")
CI_REFERENCE = Path(".github/CI.md")


def _endor_job(workflow: str) -> str:
    start = workflow.index("  endor:\n")
    return workflow[start:]


def _lines_before_checkout(job: str) -> str:
    marker = "      - name: Check out Ultra CSM"
    assert marker in job
    return job[: job.index(marker)]


def _step_block(job: str, name: str, following_name: str | None = None) -> str:
    marker = f"      - name: {name}"
    assert marker in job
    start = job.index(marker)
    if following_name is None:
        return job[start:]
    following_marker = f"      - name: {following_name}"
    assert following_marker in job[start + len(marker) :]
    end = job.index(following_marker, start + len(marker))
    return job[start:end]


def _assert_endor_contract(job: str) -> None:
    assert "if: ${{ vars.ENDOR_ENABLED == 'true' }}" in job
    assert "Skip notice when Endor is not configured" not in job
    assert "ENDOR_TOKEN not set; skipping" not in job
    preflight = _step_block(job, "Validate Endor configuration", "Check out Ultra CSM")
    checkout = _step_block(job, "Check out Ultra CSM", "Endor scan")
    scan = _step_block(job, "Endor scan")

    assert "Validate Endor configuration" in preflight
    assert "ENDOR_TOKEN" in preflight
    assert "ENDOR_NAMESPACE" in preflight
    assert "exit 1" in preflight
    assert "uses: actions/checkout" not in preflight
    assert "if: ${{ always() }}" not in job
    assert "continue-on-error" not in job
    assert "if:" not in preflight
    assert "if:" not in checkout
    assert "if:" not in scan
    assert "uses: endorlabs/github-action@" in scan


def test_unconfigured_job_is_not_selected() -> None:
    _assert_endor_contract(_endor_job(WORKFLOW.read_text()))


def test_incomplete_enabled_configuration_fails_before_checkout() -> None:
    _assert_endor_contract(_endor_job(WORKFLOW.read_text()))


def test_documented_states() -> None:
    reference = CI_REFERENCE.read_text().lower()

    for state in ("passed", "failed", "not configured", "unverified"):
        assert state in reference
    assert "is not a passed scan" in reference


def test_rejects_successful_noop() -> None:
    former_noop = """  endor:
    runs-on: ubuntu-24.04
    steps:
      - name: Skip notice when Endor is not configured
        run: echo 'skipping'
"""

    with pytest.raises(AssertionError):
        _assert_endor_contract(former_noop)


def test_rejects_enabled_bypass() -> None:
    enabled_bypass = """  endor:
    if: ${{ vars.ENDOR_ENABLED == 'true' }}
    runs-on: ubuntu-24.04
    steps:
      - name: Validate Endor configuration
        run: exit 1
        continue-on-error: true
      - name: Check out Ultra CSM
        uses: actions/checkout@deadbeef
      - name: Endor scan
        uses: endorlabs/github-action@deadbeef
"""

    with pytest.raises(AssertionError):
        _assert_endor_contract(enabled_bypass)


def test_rejects_conditional_scan() -> None:
    conditional_scan = """  endor:
    if: ${{ vars.ENDOR_ENABLED == 'true' }}
    runs-on: ubuntu-24.04
    steps:
      - name: Validate Endor configuration
        run: |
          if [ -z "$ENDOR_TOKEN" ] || [ -z "$ENDOR_NAMESPACE" ]; then
            exit 1
          fi
      - name: Check out Ultra CSM
        uses: actions/checkout@deadbeef
      - name: Endor scan
        if: ${{ success() }}
        uses: endorlabs/github-action@deadbeef
"""

    with pytest.raises(AssertionError):
        _assert_endor_contract(conditional_scan)
