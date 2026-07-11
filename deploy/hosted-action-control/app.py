"""Vercel entrypoint for the isolated persistent Action Control sandbox."""

from __future__ import annotations

import os

if os.environ.get("ULTRA_CSM_DATABASE_ADMIN_URL"):
    raise RuntimeError("database admin credentials are forbidden in the hosted runtime")
if not os.environ.get("ULTRA_CSM_DATABASE_URL"):
    raise RuntimeError("ULTRA_CSM_DATABASE_URL is required in the hosted runtime")
if not os.environ.get("ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS"):
    raise RuntimeError("ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS is required in the hosted runtime")

from ultra_csm.action_control_sandbox_api import app  # noqa: E402

__all__ = ["app"]
