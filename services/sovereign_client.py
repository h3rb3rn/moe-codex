"""HTTP client for the moe-sovereign core.

The Codex backend calls moe-sovereign only at clearly defined boundaries:
- GET  /graph/stats              — for drift snapshots
- POST /graph/knowledge/import   — when an approval is granted, push the bundle through
- GET  /graph/search             — when the catalog needs to enrich a row
- GET  /graph/domains            — for the Neo4j source in /catalog

Note: moe-sovereign mounts the graph router without a `/v1` prefix.
The router prefix is configurable via SOVEREIGN_GRAPH_PREFIX (default empty).

All other Codex operations (lineage, versioning, ETL, drift) stay local.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

SOVEREIGN_URL = os.getenv("SOVEREIGN_URL", "http://moe-sovereign:8002")
SOVEREIGN_TIMEOUT = float(os.getenv("SOVEREIGN_TIMEOUT", "30"))
SOVEREIGN_API_KEY = os.getenv("SOVEREIGN_API_KEY", "")
GRAPH_PREFIX = os.getenv("SOVEREIGN_GRAPH_PREFIX", "")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SOVEREIGN_API_KEY:
        h["Authorization"] = f"Bearer {SOVEREIGN_API_KEY}"
    return h


async def graph_stats() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=SOVEREIGN_TIMEOUT) as c:
        r = await c.get(f"{SOVEREIGN_URL}{GRAPH_PREFIX}/graph/stats", headers=_headers())
        r.raise_for_status()
        return r.json()


async def graph_domains() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=SOVEREIGN_TIMEOUT) as c:
        r = await c.get(f"{SOVEREIGN_URL}{GRAPH_PREFIX}/graph/domains", headers=_headers())
        r.raise_for_status()
        return r.json()


async def knowledge_import(bundle: dict[str, Any], source_tag: str,
                           trust_floor: float | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"bundle": bundle, "source_tag": source_tag}
    if trust_floor is not None:
        payload["trust_floor"] = trust_floor
    async with httpx.AsyncClient(timeout=SOVEREIGN_TIMEOUT) as c:
        r = await c.post(
            f"{SOVEREIGN_URL}{GRAPH_PREFIX}/graph/knowledge/import",
            json=payload, headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


async def health_check() -> bool:
    """Lightweight reachability probe used by /health and the admin UI banner."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{SOVEREIGN_URL}/health", headers=_headers())
            return r.status_code == 200
    except Exception:
        return False
