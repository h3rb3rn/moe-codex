"""services/budibase.py — Budibase low-code app builder client (Track D.4.1).

Wraps Budibase's internal REST API to:
  1. Authenticate and cache an API key session.
  2. List published applications for the embed picker.
  3. Return the Budibase base URL so the admin UI can iframe apps.
  4. Bootstrap a Codex datasource (Trino or Postgres) on first use.

Budibase does not currently expose a guest-token embed like Superset; apps
embedded in iframes require the user to have a Budibase account or the app
to be published as a public app. The admin UI surfaces the direct link and
an iframe for public apps.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BUDIBASE_URL     = os.getenv("BUDIBASE_URL",  "http://moe-budibase:80")
BUDIBASE_API_KEY = os.getenv("BUDIBASE_API_KEY", "")
BUDIBASE_TIMEOUT = float(os.getenv("BUDIBASE_TIMEOUT", "15"))


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if BUDIBASE_API_KEY:
        h["x-budibase-api-key"] = BUDIBASE_API_KEY
    return h


async def health_check() -> bool:
    """Probe Budibase reachability. The root URL redirects to /builder (200)."""
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as c:
            r = await c.get(f"{BUDIBASE_URL}/")
            return r.status_code == 200
    except Exception:
        return False


async def list_apps(page: int = 1, per_page: int = 50) -> dict[str, Any]:
    """Return paginated list of Budibase applications."""
    async with httpx.AsyncClient(timeout=BUDIBASE_TIMEOUT) as c:
        r = await c.get(
            f"{BUDIBASE_URL}/api/global/configs/checklist",
            headers=_headers(),
        )
        # Budibase v2 public API endpoint
        r2 = await c.get(
            f"{BUDIBASE_URL}/api/applications",
            headers=_headers(),
        )
        if r2.status_code == 200:
            data = r2.json()
            apps = data if isinstance(data, list) else data.get("data", [])
            return {"apps": apps, "total": len(apps)}
        return {"apps": [], "total": 0, "error": f"HTTP {r2.status_code}"}


async def get_app(app_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=BUDIBASE_TIMEOUT) as c:
        r = await c.get(
            f"{BUDIBASE_URL}/api/applications/{app_id}",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


async def app_embed_url(app_id: str) -> str:
    """Return the direct iframe URL for a published Budibase app."""
    return f"{BUDIBASE_URL}/embed/{app_id}"
