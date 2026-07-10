from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import psycopg
from psycopg.conninfo import make_conninfo
import pytest

from scripts.bootstrap_hosted_action_control_db import (
    ADMIN_ENV,
    bootstrap,
    RUNTIME_ENV,
    validated_dsns,
)
from ultra_csm.platform import EphemeralCluster
from ultra_csm.action_control_sandbox_api import _allowed_origins

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_hosted_action_control_bundle.py"
TRACKED_MANIFEST = ROOT / "deploy" / "hosted-action-control" / "manifest.json"
EXPECTED_ROUTES = {
    ("/openapi.json", ("GET", "HEAD")),
    ("/docs", ("GET", "HEAD")),
    ("/docs/oauth2-redirect", ("GET", "HEAD")),
    ("/redoc", ("GET", "HEAD")),
    ("/health", ("GET",)),
    ("/demo/action-control/sandbox/evaluate", ("POST",)),
}


def test_two_clean_bundle_builds_are_byte_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _build(first)
    _build(second)

    assert _tree_hashes(first) == _tree_hashes(second)
    assert (first / ".bundle-manifest.json").read_bytes() == TRACKED_MANIFEST.read_bytes()


def test_builder_refuses_source_tree_as_output():
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "refusing unsafe bundle output path" in result.stderr


def test_bundle_builds_from_git_index_without_worktree_or_local_dependencies(tmp_path):
    checkout = tmp_path / "clean-checkout"
    checkout.mkdir()
    subprocess.run(
        ["git", "checkout-index", "--all", f"--prefix={checkout.as_posix()}/"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "clean-bundle"
    subprocess.run(
        [
            sys.executable,
            str(checkout / "scripts" / "build_hosted_action_control_bundle.py"),
            "--output",
            str(output),
        ],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output / ".bundle-manifest.json").read_bytes() == (
        checkout / "deploy" / "hosted-action-control" / "manifest.json"
    ).read_bytes()


def test_bundle_contains_only_manifested_runtime_surface(tmp_path):
    bundle = tmp_path / "bundle"
    _build(bundle)
    manifest = json.loads(TRACKED_MANIFEST.read_text(encoding="utf-8"))
    actual = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()}

    assert actual == set(manifest["files"]) | {".bundle-manifest.json"}
    assert manifest["source_bytes"] <= manifest["source_budget_bytes"]
    assert manifest["entrypoint"] == "app.py:app"
    assert manifest["external_effects_enabled"] is False
    assert manifest["admin_database_credentials_accepted"] is False
    assert manifest["vercel_python_uncompressed_limit_bytes"] == 500 * 1024 * 1024
    assert not any(
        name.startswith(("ui/", "tests/", "eval/", "ultra_csm/data_plane/")) for name in actual
    )
    assert "ultra_csm/api.py" not in actual
    assert "ultra_csm/mcp_server.py" not in actual
    assert "ultra_csm/committers.py" not in actual
    assert "ULTRA_CSM_DATABASE_ADMIN_URL=" not in (bundle / ".env.example").read_text()

    requirements = (bundle / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert requirements
    assert all("==" in requirement for requirement in requirements)
    assert not any(
        "uvicorn" in requirement or "httpx" in requirement for requirement in requirements
    )

    config = json.loads((bundle / "vercel.json").read_text(encoding="utf-8"))
    function = config["functions"]["app.py"]
    assert function["includeFiles"] == "migrations/**"
    assert function["maxDuration"] == 30
    assert "rewrites" not in config
    assert "routes" not in config


def test_bundled_app_imports_with_exact_minimal_routes(tmp_path):
    bundle = tmp_path / "bundle"
    _build(bundle)
    script = """
import json
from app import app
print(json.dumps(sorted((route.path, sorted(route.methods or [])) for route in app.routes)))
"""
    result = _bundle_python(bundle, script)
    routes = {(path, tuple(methods)) for path, methods in json.loads(result.stdout)}

    assert routes == EXPECTED_ROUTES


def test_bundled_entrypoint_rejects_admin_credentials(tmp_path):
    bundle = tmp_path / "bundle"
    _build(bundle)
    env = _bundle_env()
    env[ADMIN_ENV] = "postgresql://admin:SECRET_SENTINEL@db.invalid/demo"
    result = subprocess.run(
        [sys.executable, "-c", "from app import app"],
        cwd=bundle,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "admin credentials are forbidden" in result.stderr
    assert "SECRET_SENTINEL" not in result.stderr


def test_bundle_has_no_machine_paths_secrets_or_nonsynthetic_email(tmp_path):
    bundle = tmp_path / "bundle"
    _build(bundle)
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in bundle.rglob("*")
        if path.is_file() and path.name != ".bundle-manifest.json"
    )

    assert str(ROOT) not in text
    assert "/Users/" not in text
    assert "/home/" not in text
    assert "BEGIN PRIVATE KEY" not in text
    assert not re.search(r"(?i)(?:sk|ghp|vercel)_[a-z0-9_-]{20,}", text)
    assert not re.search(r"postgres(?:ql)?://[^\s:]+:[^\s@]+@", text)
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", text)
    assert all(email.endswith(".example") for email in emails)


def test_bootstrap_creates_passworded_rls_safe_runtime_role():
    password = "local-test-password-0123456789"
    with EphemeralCluster() as cluster:
        admin_url = make_conninfo("", **cluster.dsn(user=cluster.BOOTSTRAP_USER))
        runtime_url = make_conninfo(
            "",
            **cluster.dsn(user="app_runtime"),
            password=password,
        )
        bootstrap({ADMIN_ENV: admin_url, RUNTIME_ENV: runtime_url})
        with psycopg.connect(admin_url) as admin:
            role = admin.execute(
                "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, "
                "rolcreaterole, rolreplication, rolconnlimit FROM pg_roles "
                "WHERE rolname = 'app_runtime'"
            ).fetchone()

    assert role == (True, False, False, False, False, False, 10)


def test_bootstrap_dsn_validation_never_accepts_admin_runtime_alias():
    dsn = "postgresql://app_runtime:local-test-password-0123456789@db.invalid/demo"
    try:
        validated_dsns({ADMIN_ENV: dsn, RUNTIME_ENV: dsn})
    except RuntimeError as exc:
        assert str(exc) == "admin and runtime DSNs must be different"
        assert "password" not in str(exc).lower()
    else:
        raise AssertionError("identical admin/runtime DSNs were accepted")


def test_persistent_cors_accepts_one_exact_https_origin(monkeypatch):
    monkeypatch.setenv(RUNTIME_ENV, "postgresql://app_runtime:test@db.invalid/demo")
    monkeypatch.setenv("ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS", "https://ui.example.test/")

    assert _allowed_origins() == ["https://ui.example.test"]


@pytest.mark.parametrize(
    "origin",
    (
        "http://ui.example.test",
        "https://*.example.test",
        "https://ui.example.test/path",
        "https://one.example.test,https://two.example.test",
    ),
)
def test_persistent_cors_rejects_nonexact_origins(monkeypatch, origin):
    monkeypatch.setenv(RUNTIME_ENV, "postgresql://app_runtime:test@db.invalid/demo")
    monkeypatch.setenv("ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS", origin)

    with pytest.raises(RuntimeError):
        _allowed_origins()


def _build(output: Path) -> None:
    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _bundle_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    env[RUNTIME_ENV] = "postgresql://app_runtime:abcdefghijklmnopqrstuvwxyz@db.invalid/demo"
    env["ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS"] = "https://ui.example.test"
    env.pop(ADMIN_ENV, None)
    return env


def _bundle_python(bundle: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=bundle,
        env=_bundle_env(),
        capture_output=True,
        text=True,
        check=True,
    )
