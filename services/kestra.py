"""services/kestra.py — Kestra workflow orchestrator client (Phase D.2.1).

Thin HTTP wrapper around Kestra's REST API. All methods return plain dicts
or raise httpx.HTTPStatusError on non-2xx responses; callers handle errors.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

KESTRA_URL     = os.getenv("KESTRA_URL", "http://moe-kestra:8080")
KESTRA_TIMEOUT = float(os.getenv("KESTRA_TIMEOUT", "15"))
KESTRA_ENABLED = bool(KESTRA_URL)

_HEADERS = {"Content-Type": "application/json"}


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{KESTRA_URL}/api/v1/flows/search", params={"size": 1})
            return r.status_code == 200
    except Exception:
        return False


async def list_flows(namespace: str = "", page: int = 1, size: int = 50) -> dict[str, Any]:
    params: dict = {"page": page, "size": size}
    if namespace:
        params["namespace"] = namespace
    async with httpx.AsyncClient(timeout=KESTRA_TIMEOUT) as c:
        r = await c.get(f"{KESTRA_URL}/api/v1/flows/search", params=params)
        r.raise_for_status()
        return r.json()


async def get_flow(namespace: str, flow_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=KESTRA_TIMEOUT) as c:
        r = await c.get(f"{KESTRA_URL}/api/v1/flows/{namespace}/{flow_id}")
        r.raise_for_status()
        return r.json()


async def trigger_flow(namespace: str, flow_id: str, inputs: dict | None = None) -> dict[str, Any]:
    """Create a new execution for the given flow."""
    async with httpx.AsyncClient(timeout=KESTRA_TIMEOUT) as c:
        r = await c.post(
            f"{KESTRA_URL}/api/v1/executions/{namespace}/{flow_id}",
            json=inputs or {},
            headers=_HEADERS,
        )
        r.raise_for_status()
        return r.json()


async def list_executions(namespace: str = "", flow_id: str = "",
                          page: int = 1, size: int = 50) -> dict[str, Any]:
    params: dict = {"page": page, "size": size}
    if namespace: params["namespace"] = namespace
    if flow_id:   params["flowId"]    = flow_id
    async with httpx.AsyncClient(timeout=KESTRA_TIMEOUT) as c:
        r = await c.get(f"{KESTRA_URL}/api/v1/executions/search", params=params)
        r.raise_for_status()
        return r.json()


async def get_execution(execution_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=KESTRA_TIMEOUT) as c:
        r = await c.get(f"{KESTRA_URL}/api/v1/executions/{execution_id}")
        r.raise_for_status()
        return r.json()
