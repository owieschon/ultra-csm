"""Non-reflective HTTP error responses for the public synthetic sandbox."""

from __future__ import annotations

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


NO_STORE_HEADERS = {"Cache-Control": "no-store"}

_SAFE_SANDBOX_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "expected_state_sha256",
        "commands",
        "command_id",
        "type",
        "draft",
    }
)


def safe_validation_field_paths(exc: RequestValidationError) -> list[str]:
    """Return only server-declared field names and numeric collection indexes."""

    paths: set[str] = set()
    for error in exc.errors():
        parts: list[str] = []
        for component in error.get("loc", ()):
            if component == "body":
                continue
            if isinstance(component, int) and component >= 0:
                parts.append(str(component))
            elif isinstance(component, str) and component in _SAFE_SANDBOX_FIELDS:
                parts.append(component)
        paths.add(".".join(parts) if parts else "request")
    return sorted(paths or {"request"})


def validation_error_response(
    exc: RequestValidationError,
    *,
    code: str = "INVALID_SANDBOX_REQUEST",
) -> JSONResponse:
    """Build a stable 422 without rejected values, messages, or attacker keys."""

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": code,
                "fields": safe_validation_field_paths(exc),
            }
        },
        headers=NO_STORE_HEADERS,
    )


def internal_error_response() -> JSONResponse:
    """Return a stable failure envelope without exception text."""

    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "SANDBOX_INTERNAL_ERROR",
                "error": "Sandbox evaluation failed safely.",
            }
        },
        headers=NO_STORE_HEADERS,
    )
