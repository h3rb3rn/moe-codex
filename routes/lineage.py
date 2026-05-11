"""Lineage events & runs (Marquez proxy, Phase 16)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.lineage import _emit, _enabled as lineage_enabled

router = APIRouter()

MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://moe-marquez:5000")


@router.post("/lineage/event")
async def lineage_event(raw_request: Request):
    """Receive an OpenLineage event from moe-sovereign and forward to Marquez."""
    if not lineage_enabled():
        return JSONResponse(status_code=503, content={"error": "MARQUEZ_URL not set"})
    try:
        event = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    await _emit(event)
    return {"status": "ok"}


@router.get("/lineage/runs")
async def lineage_runs(namespace: str = "moe", job: str | None = None, limit: int = 20):
    """List recent lineage runs from Marquez."""
    if not lineage_enabled():
        return {"runs": [], "status": "disabled"}
    async with httpx.AsyncClient(timeout=10) as c:
        path = (
            f"{MARQUEZ_URL}/api/v1/namespaces/{namespace}/jobs/{job}/runs"
            if job else f"{MARQUEZ_URL}/api/v1/namespaces/{namespace}/jobs"
        )
        r = await c.get(path, params={"limit": limit})
        if r.status_code != 200:
            return {"runs": [], "status": "error", "code": r.status_code}
        return {"runs": r.json(), "status": "ok"}
