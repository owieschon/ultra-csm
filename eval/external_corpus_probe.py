"""Runtime-only probe for an externally relayed customer book.

The probe is generic and contains no corpus-specific defaults. Raw records,
source-map proposals, confirmations, and run artifacts are written outside the
repository because they may contain private source details.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
from urllib.parse import quote

from ultra_csm.data_plane.external_book import (
    ExternalSourceDescriptor,
    ingest_external_book,
    propose_external_source_mapping,
)
from ultra_csm.data_plane.source_mapping import (
    load_mapping_confirmations,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = Path.home() / "ultra-csm-corpus-runs"
DEFAULT_LIMIT = 200
DEFAULT_PAGE_SIZE = 100
API_KEY_ENV = "CORPUS_A_" "API_KEY"


class ExternalCorpusProbeError(RuntimeError):
    """The runtime probe could not complete safely."""


def run_external_corpus_probe(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    confirmations_path: Path | None = None,
    limit: int = DEFAULT_LIMIT,
    page_size: int = DEFAULT_PAGE_SIZE,
    run_label: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    _assert_outside_repo(output_root)
    run_id = run_label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / run_id
    _assert_outside_repo(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)

    records, fetch_summary = _fetch_records(
        env=env,
        limit=max(0, limit),
        page_size=max(1, page_size),
        run_dir=run_dir,
    )
    descriptor = ExternalSourceDescriptor(
        source_name="external_corpus_runtime",
        expected_count=fetch_summary.get("source_reported_count"),
        max_records=max(0, limit),
    )
    snapshot, proposal, unrepresentable = propose_external_source_mapping(
        records,
        descriptor,
    )
    proposal_path = run_dir / "mapping_proposal.json"
    proposal_path.write_text(
        json.dumps(proposal.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_confirmation_template(proposal, run_dir / "confirmation_template.json")

    frozen = None
    if confirmations_path is not None:
        _assert_outside_repo(confirmations_path)
        confirmations = load_mapping_confirmations(confirmations_path)
        from ultra_csm.data_plane.source_mapping import freeze_confirmed_source_map

        frozen = freeze_confirmed_source_map(proposal, confirmations=confirmations)

    result = ingest_external_book(records, descriptor, frozen_map=frozen)
    coverage_path = run_dir / "coverage.json"
    coverage_path.write_text(
        json.dumps(result.coverage.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    briefing_path = run_dir / "briefing.txt"
    briefing_path.write_text("\n".join(result.briefing) + "\n", encoding="utf-8")

    summary = _sanitized_summary(
        fetch_summary=fetch_summary,
        proposal=proposal,
        unrepresentable=unrepresentable,
        result=result,
        confirmations_path=confirmations_path,
        run_dir=run_dir,
    )
    summary_path = run_dir / "sanitized_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _fetch_records(
    *,
    env: Mapping[str, str],
    limit: int,
    page_size: int,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_url = _required_env(env, "CORPUS_A_BASE_URL").rstrip("/")
    table = _required_env(env, "CORPUS_A_TABLE").strip("/")
    api_key = _required_env(env, API_KEY_ENV)
    records: list[dict[str, Any]] = []
    source_reported_count: int | None = None
    started = datetime.now(timezone.utc)
    offset = 0
    page_index = 0
    while offset < limit:
        current_limit = min(page_size, limit - offset)
        if current_limit <= 0:
            break
        body, headers = _curl_page(
            base_url=base_url,
            table=table,
            api_key=api_key,
            limit=current_limit,
            offset=offset,
            header_path=run_dir / f"headers_{page_index:04d}.txt",
        )
        page = json.loads(body)
        if not isinstance(page, list):
            raise ExternalCorpusProbeError("external source returned a non-list payload")
        for item in page:
            if not isinstance(item, dict):
                raise ExternalCorpusProbeError("external source returned a non-object row")
        records.extend(page)
        count = _content_range_count(headers)
        if count is not None:
            source_reported_count = count
        offset += len(page)
        page_index += 1
        if len(page) < current_limit:
            break
        if source_reported_count is not None and len(records) >= min(limit, source_reported_count):
            break

    raw_path = run_dir / "raw_records.json"
    raw_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    return records, {
        "rows_fetched": len(records),
        "source_reported_count": source_reported_count,
        "fetched_all_reported_rows": (
            source_reported_count is not None
            and len(records) >= source_reported_count
        ),
        "probe_limit": limit,
        "page_size": page_size,
        "pages": page_index,
        "wall_ms": elapsed_ms,
        "raw_records_path": str(raw_path),
    }


def _curl_page(
    *,
    base_url: str,
    table: str,
    api_key: str,
    limit: int,
    offset: int,
    header_path: Path,
) -> tuple[str, str]:
    url = f"{base_url}/{quote(table, safe='/')}"
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--get",
        url,
        "--header",
        f"apikey: {api_key}",
        "--header",
        f"Authorization: Bearer {api_key}",
        "--header",
        "Prefer: count=exact",
        "--data-urlencode",
        "select=*",
        "--data-urlencode",
        f"limit={limit}",
        "--data-urlencode",
        f"offset={offset}",
        "--dump-header",
        str(header_path),
    ]
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise ExternalCorpusProbeError(
            "external source read failed; check private credentials and endpoint liveness"
        ) from None
    return proc.stdout, header_path.read_text(encoding="utf-8")


def _content_range_count(headers: str) -> int | None:
    for line in headers.splitlines():
        if not line.lower().startswith("content-range:"):
            continue
        match = re.search(r"/(\d+|\*)\s*$", line)
        if match and match.group(1) != "*":
            return int(match.group(1))
    return None


def _write_confirmation_template(proposal, path: Path) -> None:  # noqa: ANN001
    template = {
        "confirmations": {
            entry.key: {
                "contract": entry.contract,
                "internal_field": entry.internal_field,
                "source_object": entry.source_object,
                "source_field": entry.source_field,
                "source_path": entry.source_path,
                "semantic_role": entry.semantic_role,
                "value_direction": (
                    "higher_is_better"
                    if entry.value_direction in {"ordered_confirm", "direction_confirm"}
                    else "not_applicable"
                ),
            }
            for entry in proposal.entries
            if entry.state == "ambiguous_confirm"
        }
    }
    path.write_text(json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitized_summary(
    *,
    fetch_summary: dict[str, Any],
    proposal,
    unrepresentable: tuple[str, ...],
    result,
    confirmations_path: Path | None,
    run_dir: Path,
) -> dict[str, Any]:
    rows_fetched = int(fetch_summary["rows_fetched"])
    source_count = fetch_summary["source_reported_count"]
    return {
        "artifact": "external_corpus_probe_summary",
        "claim_boundary": {
            "runtime_private_corpus": True,
            "committable": False,
            "raw_outputs_outside_repo": True,
        },
        "run_dir": str(run_dir),
        "relay_fidelity": {
            "rows_fetched": rows_fetched,
            "source_reported_count": source_count,
            "fetched_all_reported_rows": fetch_summary["fetched_all_reported_rows"],
            "probe_limit": fetch_summary["probe_limit"],
            "pages": fetch_summary["pages"],
        },
        "mapping": {
            "coverage": proposal.coverage,
            "silent_guess_count": proposal.coverage.get("mapped", 0),
            "requires_confirmation_count": proposal.coverage.get("ambiguous_confirm", 0),
            "missing_to_unknown_count": proposal.coverage.get("missing_to_unknown", 0),
            "confirmations_loaded": confirmations_path is not None,
        },
        "ingest": {
            "records_processed": result.coverage.records_processed,
            "records_typed": result.coverage.records_typed,
            "records_rejected_count": len(result.coverage.records_rejected),
            "rejection_counts": result.coverage.rejection_counts,
            "join_coverage": result.coverage.join_coverage,
            "count_mismatch": result.coverage.count_mismatch,
            "truncated": result.coverage.truncated,
            "injection_marker_count": result.coverage.injection_marker_count,
        },
        "shape_limits": {
            "unrepresentable_path_count": len(unrepresentable),
        },
        "scoring_readiness": {
            "typed_crm_accounts": result.coverage.records_typed.get("CRMAccount", 0),
            "work_item_scorer_ran": False,
            "scoreable_accounts": 0,
            "reason": (
                "CRM-only ingest lacks CS-platform health, onboarding, outcome, "
                "and product-telemetry rails; work-item scoring would be hollow."
            ),
        },
        "briefing": {
            "line_count": len(result.briefing),
            "crm_only_degradation_noted": any(
                "CRM-only ingest" in line for line in result.briefing
            ),
        },
        "timing": {
            "wall_ms": fetch_summary["wall_ms"],
        },
    }


def _required_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise ExternalCorpusProbeError(f"required environment variable is missing: {name}")
    return value


def _assert_outside_repo(path: Path) -> None:
    resolved = path.expanduser().resolve()
    repo = REPO.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        return
    raise ExternalCorpusProbeError(f"{resolved} is inside the repository")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--confirmations", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--run-label", default=None)
    args = parser.parse_args(argv)
    summary = run_external_corpus_probe(
        output_root=args.output_root,
        confirmations_path=args.confirmations,
        limit=args.limit,
        page_size=args.page_size,
        run_label=args.run_label,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
