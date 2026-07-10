"""Build the allowlisted, deterministic hosted Action Control deployment bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Final

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "deploy" / "hosted-action-control"
TRACKED_MANIFEST = TEMPLATE_ROOT / "manifest.json"
DEFAULT_OUTPUT = ROOT / "build" / "hosted-action-control"
SOURCE_BUDGET_BYTES: Final = 512 * 1024

TEMPLATE_FILES: Final = (
    ".env.example",
    ".python-version",
    ".vercelignore",
    "app.py",
    "requirements.txt",
    "vercel.json",
)
SOURCE_FILES: Final = (
    "src/ultra_csm/__init__.py",
    "src/ultra_csm/action_control_contract.py",
    "src/ultra_csm/action_control_sandbox.py",
    "src/ultra_csm/action_control_sandbox_api.py",
    "src/ultra_csm/action_control_sandbox_committer.py",
    "src/ultra_csm/action_control_sandbox_contract.py",
    "src/ultra_csm/action_control_sandbox_fixture.py",
    "src/ultra_csm/action_control_sandbox_http.py",
    "src/ultra_csm/action_control_sandbox_runtime.py",
    "src/ultra_csm/governance/__init__.py",
    "src/ultra_csm/governance/authorizer.py",
    "src/ultra_csm/governance/csm_actions.py",
    "src/ultra_csm/governance/gate.py",
    "src/ultra_csm/platform/db.py",
    "src/ultra_csm/platform/seed.py",
)
PACKAGE_MARKERS: Final = {
    "ultra_csm/platform/__init__.py": (
        b'"""Deployment package marker; local Postgres process controls are excluded."""\n'
    ),
}


def _migration_files() -> tuple[str, ...]:
    return tuple(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "migrations").glob("[0-9]*_*.sql"))
    )


def _output_files() -> dict[str, bytes]:
    files = {name: (TEMPLATE_ROOT / name).read_bytes() for name in TEMPLATE_FILES}
    for source_name in (*SOURCE_FILES, *_migration_files()):
        source_path = ROOT / source_name
        if source_path.is_symlink() or not source_path.is_file():
            raise RuntimeError(f"bundle input must be a regular tracked file: {source_name}")
        if source_name.startswith("src/"):
            output_name = source_name.removeprefix("src/")
        else:
            output_name = source_name
        files[output_name] = source_path.read_bytes()
    files.update(PACKAGE_MARKERS)
    return dict(sorted(files.items()))


def build_manifest(files: dict[str, bytes]) -> dict:
    entries = {
        name: {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for name, content in files.items()
    }
    total_bytes = sum(entry["bytes"] for entry in entries.values())
    aggregate = hashlib.sha256(
        b"".join(
            name.encode() + b"\0" + entries[name]["sha256"].encode() + b"\n"
            for name in sorted(entries)
        )
    ).hexdigest()
    return {
        "schema_version": "ultra.hosted-action-control-bundle.v1",
        "entrypoint": "app.py:app",
        "python": "3.12",
        "external_effects_enabled": False,
        "runtime_database_env": "ULTRA_CSM_DATABASE_URL",
        "admin_database_credentials_accepted": False,
        "vercel_python_uncompressed_limit_bytes": 500 * 1024 * 1024,
        "source_budget_bytes": SOURCE_BUDGET_BYTES,
        "source_bytes": total_bytes,
        "aggregate_sha256": aggregate,
        "files": entries,
    }


def _manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()


def write_bundle(output: Path, files: dict[str, bytes], manifest: dict) -> None:
    if output.is_symlink():
        raise RuntimeError(f"refusing symlink bundle output path: {output}")
    output = output.resolve()
    forbidden = {Path("/"), Path.home().resolve(), ROOT.resolve(), TEMPLATE_ROOT.resolve()}
    if output in forbidden or output.is_relative_to(TEMPLATE_ROOT.resolve()):
        raise RuntimeError(f"refusing unsafe bundle output path: {output}")
    if output.exists():
        shutil.rmtree(output)
    for name, content in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    (output / ".bundle-manifest.json").write_bytes(_manifest_bytes(manifest))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.check and args.write_manifest:
        raise SystemExit("--check and --write-manifest are mutually exclusive")
    files = _output_files()
    manifest = build_manifest(files)
    if manifest["source_bytes"] > SOURCE_BUDGET_BYTES:
        raise SystemExit(
            f"bundle source budget exceeded: {manifest['source_bytes']} > {SOURCE_BUDGET_BYTES}"
        )
    expected = _manifest_bytes(manifest)
    if args.check:
        if not TRACKED_MANIFEST.exists() or TRACKED_MANIFEST.read_bytes() != expected:
            print("hosted Action Control bundle manifest is stale")
            print("run: python3 scripts/build_hosted_action_control_bundle.py --write-manifest")
            return 1
        print(
            "hosted Action Control bundle manifest is current "
            f"({manifest['source_bytes']} source bytes)"
        )
        return 0
    if args.write_manifest:
        TRACKED_MANIFEST.write_bytes(expected)
        print(f"wrote {TRACKED_MANIFEST.relative_to(ROOT)}")
        return 0
    if not TRACKED_MANIFEST.exists() or TRACKED_MANIFEST.read_bytes() != expected:
        print("refusing to build from source that differs from the tracked manifest")
        print("review changes, then run with --write-manifest intentionally")
        return 1
    write_bundle(args.output, files, manifest)
    print(
        f"built {args.output} ({len(files)} files, {manifest['source_bytes']} source bytes, "
        f"sha256={manifest['aggregate_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
