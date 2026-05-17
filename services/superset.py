"""services/superset.py — Apache Superset client (Track D.3.1, Quiver parity).

Wraps Superset's REST API to:
  1. Authenticate and cache a short-lived bearer token.
  2. List published dashboards for the embed picker.
  3. Issue guest tokens so the admin UI can render dashboards in an iframe
     without exposing Superset credentials to the browser.
  4. Register the bundled Trino connection so analysts have a query target
     on first boot.

All calls are async; callers handle exceptions.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SUPERSET_URL   = os.getenv("SUPERSET_URL", "http://moe-superset:8088")
SUPERSET_USER  = os.getenv("SUPERSET_ADMIN_USER", "admin")
SUPERSET_PASS  = os.getenv("SUPERSET_ADMIN_PASS", "SovereignBI!")
SUPERSET_TIMEOUT = float(os.getenv("SUPERSET_TIMEOUT", "15"))
TRINO_URL      = os.getenv("TRINO_URL", "trino://moe-trino:8080/memory")

_token_cache: dict[str, Any] = {"token": None, "expires": 0.0}
_lock = asyncio.Lock()


async def _get_token() -> str:
    """Return a valid bearer token, refreshing if expired (TTL: 3 minutes)."""
    async with _lock:
        if _token_cache["token"] and time.monotonic() < _token_cache["expires"]:
            return _token_cache["token"]
        async with httpx.AsyncClient(timeout=SUPERSET_TIMEOUT) as c:
            r = await c.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json={
                    "username": SUPERSET_USER,
                    "password": SUPERSET_PASS,
                    "provider": "db",
                    "refresh":  True,
                },
            )
            r.raise_for_status()
            token = r.json()["access_token"]
            _token_cache["token"]   = token
            _token_cache["expires"] = time.monotonic() + 180
            return token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{SUPERSET_URL}/health")
            return r.status_code == 200 and r.text.strip() == "OK"
    except Exception:
        return False


async def list_dashboards(page: int = 0, page_size: int = 50) -> dict[str, Any]:
    """Return paginated list of published dashboards."""
    token = await _get_token()
    async with httpx.AsyncClient(timeout=SUPERSET_TIMEOUT) as c:
        r = await c.get(
            f"{SUPERSET_URL}/api/v1/dashboard/",
            params={
                "q": f'{{"page":{page},"page_size":{page_size},'
                     f'"filters":[{{"col":"published","opr":"DashboardIs","val":"published"}}]}}',
            },
            headers=_headers(token),
        )
        r.raise_for_status()
        return r.json()


async def guest_token(dashboard_id: int, user_info: dict | None = None) -> str:
    """Issue a short-lived guest token for embedding a dashboard in an iframe.

    user_info: optional dict with 'username', 'first_name', 'last_name'.
    """
    token = await _get_token()
    payload = {
        "user": {
            "username":   (user_info or {}).get("username", "codex-viewer"),
            "first_name": (user_info or {}).get("first_name", "Codex"),
            "last_name":  (user_info or {}).get("last_name",  "Viewer"),
        },
        "resources": [{"type": "dashboard", "id": str(dashboard_id)}],
        "rls": [],
    }
    async with httpx.AsyncClient(timeout=SUPERSET_TIMEOUT) as c:
        r = await c.post(
            f"{SUPERSET_URL}/api/v1/security/guest_token/",
            json=payload,
            headers=_headers(token),
        )
        r.raise_for_status()
        return r.json()["token"]


async def ensure_trino_db() -> dict[str, Any]:
    """Register the Trino connection in Superset if it does not exist yet.

    Idempotent: no-ops if a connection named 'Codex Trino' already exists.
    """
    token = await _get_token()
    name = "Codex Trino"

    async with httpx.AsyncClient(timeout=SUPERSET_TIMEOUT) as c:
        # Check if connection exists
        r = await c.get(
            f"{SUPERSET_URL}/api/v1/database/",
            params={"q": f'{{"filters":[{{"col":"database_name","opr":"eq","val":"{name}"}}]}}'},
            headers=_headers(token),
        )
        if r.status_code == 200 and r.json().get("count", 0) > 0:
            return {"status": "exists", "name": name}

        # Create it
        payload = {
            "database_name":     name,
            "sqlalchemy_uri":    TRINO_URL,
            "expose_in_sqllab":  True,
            "allow_run_async":   True,
            "allow_dml":         False,
            "extra":             '{"engine_params": {}}',
        }
        r = await c.post(
            f"{SUPERSET_URL}/api/v1/database/",
            json=payload,
            headers=_headers(token),
        )
        r.raise_for_status()
        return {"status": "created", "name": name, "id": r.json().get("id")}
