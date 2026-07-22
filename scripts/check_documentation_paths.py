"""Find broken high-confidence repository paths in active documentation."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT_DOCUMENTS = ("README.md", "QUICKSTART.md", "SECURITY.md")
EXCLUDED_DOCUMENT_PARTS = frozenset({"archive", "fixtures"})
REPOSITORY_PREFIXES = (
    ".github/",
    "config/",
    "deploy/",
    "docs/",
    "eval/",
    "knowledge/",
    "migrations/",
    "scripts/",
    "src/",
    "tests/",
    "ui/",
)
ROOT_FILES = frozenset(
    {
        "Makefile",
        "README.md",
        "QUICKSTART.md",
        "SECURITY.md",
        "STATUS.md",
        "pyproject.toml",
        "vercel.json",
    }
)

_FENCED_BLOCK = re.compile(r"(?ms)^```.*?^```[ \t]*$")
_INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
_REPOSITORY_PATH = re.compile(
    r"(?<![\w/])"
    r"((?:\.github|config|deploy|docs|eval|knowledge|migrations|scripts|src|tests|ui)/"
    r"[A-Za-z0-9_.@+~/-]+(?::\d+(?:-\d+)?)?)"
)
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")


@dataclass(frozen=True)
class MissingDocumentationPath:
    document: Path
    line: int
    reference: str


def active_documentation(root: Path) -> tuple[Path, ...]:
    """Return reader-facing Markdown, excluding archives and fixture inputs."""

    documents = [root / name for name in ROOT_DOCUMENTS if (root / name).is_file()]
    docs_root = root / "docs"
    if docs_root.is_dir():
        for path in docs_root.rglob("*.md"):
            relative_parts = path.relative_to(docs_root).parts[:-1]
            if EXCLUDED_DOCUMENT_PARTS.intersection(relative_parts):
                continue
            documents.append(path)
    return tuple(sorted(set(documents)))


def missing_documentation_paths(root: Path) -> tuple[MissingDocumentationPath, ...]:
    """Resolve path-like prose against the repository without guessing at commands."""

    missing: set[MissingDocumentationPath] = set()
    for document in active_documentation(root):
        text = document.read_text(encoding="utf-8")
        searchable = _FENCED_BLOCK.sub(
            lambda match: "\n" * match.group(0).count("\n"),
            text,
        )

        candidates: list[tuple[int, str]] = []
        candidates.extend(
            (match.start(1), match.group(1)) for match in _INLINE_CODE.finditer(searchable)
        )
        candidates.extend(
            (match.start(1), match.group(1)) for match in _REPOSITORY_PATH.finditer(searchable)
        )

        for match in _MARKDOWN_LINK.finditer(searchable):
            reference = _normalized_markdown_link(root, document, match.group(1))
            if reference is None or (root / reference).exists():
                continue
            missing.add(
                MissingDocumentationPath(
                    document=document.relative_to(root),
                    line=searchable.count("\n", 0, match.start(1)) + 1,
                    reference=reference,
                )
            )

        for offset, raw_reference in candidates:
            reference = _normalized_reference(raw_reference)
            if reference is None or (root / reference).exists():
                continue
            missing.add(
                MissingDocumentationPath(
                    document=document.relative_to(root),
                    line=searchable.count("\n", 0, offset) + 1,
                    reference=reference,
                )
            )
    return tuple(sorted(missing, key=lambda item: (str(item.document), item.line, item.reference)))


def _normalized_reference(raw_reference: str) -> str | None:
    reference = raw_reference.strip().rstrip(".,;:")
    if not reference or any(character.isspace() for character in reference):
        return None
    if any(marker in reference for marker in ("*", "{", "}", "<", ">", "$", "…")):
        return None

    reference = reference.split("#", 1)[0]
    reference = _LINE_SUFFIX.sub("", reference)
    if reference in ROOT_FILES:
        return reference
    if not reference.startswith(REPOSITORY_PREFIXES):
        return None

    # A suffix or trailing slash distinguishes a path claim from prose such as
    # "eval/training substrate". Missing extensionless directories are too
    # ambiguous to fail the documentation gate.
    if not reference.endswith("/") and not Path(reference).suffix:
        return None
    return reference


def _normalized_markdown_link(root: Path, document: Path, raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return None
    path = unquote(parsed.path)
    if any(marker in path for marker in ("*", "{", "}", "<", ">", "$", "…")):
        return None

    resolved = (document.parent / path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    missing = missing_documentation_paths(args.root.resolve())
    for item in missing:
        print(f"{item.document}:{item.line}: missing `{item.reference}`")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
