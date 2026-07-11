"""Minimal deployable API exposing only the synthetic Action Control sandbox."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ultra_csm.action_control_sandbox import evaluate_action_control_sandbox
from ultra_csm.action_control_sandbox_contract import (
    ActionControlSandboxRequest,
    ActionControlSandboxSession,
    SandboxError,
)
from ultra_csm.action_control_sandbox_http import (
    internal_error_response,
    NO_STORE_HEADERS,
    validation_error_response,
)
from ultra_csm.action_control_sandbox_runtime import (
    connect_persistent_runtime_database,
    persistent_database_configured,
)
from ultra_csm.platform.db import apply_migrations
from ultra_csm.platform.seed import seed


_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_MAX_REQUEST_BYTES = 16 * 1024
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cluster: Any | None = None
    if persistent_database_configured():
        if os.environ.get("ULTRA_CSM_DATABASE_ADMIN_URL"):
            raise RuntimeError(
                "ULTRA_CSM_DATABASE_ADMIN_URL is bootstrap-only and must not be "
                "present in the hosted runtime"
            )
    else:
        from ultra_csm.platform import EphemeralCluster

        cluster = EphemeralCluster().start()
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, _MIGRATIONS)
            seed(boot)
    app.state.cluster = cluster
    try:
        yield
    finally:
        if cluster is not None:
            cluster.stop()


app = FastAPI(
    title="Action Control synthetic sandbox",
    version="1.0.0",
    lifespan=lifespan,
)


def _allowed_origins() -> list[str]:
    configured = os.environ.get("ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS")
    if not persistent_database_configured():
        configured = configured or "http://localhost:3000,http://127.0.0.1:3000"
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if configured is None or "," in configured:
        raise RuntimeError(
            "persistent sandbox requires exactly one ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS value"
        )
    origin = configured.strip()
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "*" in origin
        or parsed.username is not None
    ):
        raise RuntimeError("hosted sandbox CORS origin must be one exact HTTPS origin")
    return [origin.removesuffix("/")]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
):
    return validation_error_response(exc)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    log.error(
        "Action Control sandbox request failed safely",
        extra={
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return internal_error_response()


@app.middleware("http")
async def bound_request_size(request: Request, call_next):
    length = request.headers.get("content-length")
    try:
        too_large = bool(length) and int(length) > _MAX_REQUEST_BYTES
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": {"code": "INVALID_CONTENT_LENGTH"}},
            headers=NO_STORE_HEADERS,
        )
    if too_large:
        return JSONResponse(
            status_code=413,
            content={"detail": {"code": "SANDBOX_REQUEST_TOO_LARGE"}},
            headers=NO_STORE_HEADERS,
        )
    body = await request.body()
    if len(body) > _MAX_REQUEST_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": {"code": "SANDBOX_REQUEST_TOO_LARGE"}},
            headers=NO_STORE_HEADERS,
        )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "rollback_isolated_synthetic",
        "outbound_effects_enabled": False,
    }


@app.post(
    "/demo/action-control/sandbox/evaluate",
    response_model=ActionControlSandboxSession,
)
async def evaluate(body: ActionControlSandboxRequest, response: Response):
    cluster = app.state.cluster
    connection = (
        psycopg.connect(**cluster.dsn(user="app_runtime"))
        if cluster is not None
        else connect_persistent_runtime_database()
    )
    response.headers["Cache-Control"] = "no-store"
    try:
        with connection as scenario_conn:
            return evaluate_action_control_sandbox(scenario_conn, body)
    except SandboxError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "error": str(exc), "run_id": body.run_id},
            headers={"Cache-Control": "no-store"},
        ) from exc
