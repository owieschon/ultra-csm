"""Reader-facing documentation must not point at repository paths that do not exist."""

from __future__ import annotations

from pathlib import Path

from scripts.check_documentation_paths import (
    active_documentation,
    missing_documentation_paths,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_PROCESS_DOCUMENTS = (
    "A6_HARD_GOLD_LABELING_INSTRUCTIONS.md",
    "OA_A2_ONTASK_RELABEL_INSTRUCTIONS.md",
    "OA_Q1_WRITER_ADOPTION.md",
    "QUALITY_GOLD_HARD_LAYER_SPEC.md",
    "R0_KAPPA_BAND_FINDING.md",
    "R0_RETRY_COVERAGE_FINDING.md",
    "R0_TRANSPORT_FIDELITY_FINDING.md",
    "R0_VALIDITY_RESOLUTION.md",
    "R2_TELEMETRY_RESUME_FINDING.md",
    "R2_WRITER_BAKEOFF_RESULT_CONFIRMED.md",
    "R2_WRITER_TIMEOUT_FINDING.md",
)


def test_active_documentation_paths_resolve_in_this_repository():
    assert missing_documentation_paths(ROOT) == ()


def test_completed_process_documents_are_archived_and_marked_historical():
    active = set(active_documentation(ROOT))
    archive = ROOT / "docs" / "archive" / "history"

    for name in ARCHIVED_PROCESS_DOCUMENTS:
        assert ROOT / "docs" / name not in active
        text = (archive / name).read_text(encoding="utf-8")
        assert "Historical" in "\n".join(text.splitlines()[:6])
        assert "archived 2026-07-22" in "\n".join(text.splitlines()[:6])


def test_path_check_ignores_archives_fixtures_commands_and_examples(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "docs/archive").mkdir(parents=True)
    (tmp_path / "docs/fixtures").mkdir()
    (tmp_path / "docs/current.md").write_text("Read `src/module.py:1`.\n", encoding="utf-8")
    (tmp_path / "docs/archive/old.md").write_text("See `docs/gone.md`.\n", encoding="utf-8")
    (tmp_path / "docs/fixtures/example.md").write_text(
        "See `docs/fictional.md`.\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "Natural-language eval/training is not a path claim.\n"
        "`build/generated.json`, `docs/*.md`, and `Thing.field/value` are not checked.\n"
        "[External](https://example.com/docs/missing.md) and [section](#missing) are not files.\n"
        "```sh\ncat docs/not-a-prose-reference.md\n```\n",
        encoding="utf-8",
    )

    active = {path.relative_to(tmp_path) for path in active_documentation(tmp_path)}
    assert Path("docs/archive/old.md") not in active
    assert Path("docs/fixtures/example.md") not in active
    assert missing_documentation_paths(tmp_path) == ()


def test_path_check_reports_missing_inline_and_bare_repository_paths(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/current.md").write_text(
        "Continue with [the missing guide](guide/missing.md).\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Read `docs/missing.md`, compare tests/missing_case.py:12, and open `STATUS.md`.\n",
        encoding="utf-8",
    )

    missing = missing_documentation_paths(tmp_path)

    assert [(item.line, item.reference) for item in missing] == [
        (1, "STATUS.md"),
        (1, "docs/missing.md"),
        (1, "tests/missing_case.py"),
        (1, "docs/guide/missing.md"),
    ]
