"""routes/superset.py — Apache Superset BI proxy (Track D.3.1).

POST /v1/codex/superset/setup      — register Trino connection on first boot
GET  /v1/codex/superset/dashboards — list published dashboards
GET  /v1/codex/superset/token/{id} — issue a guest token for iframe embed
GET  /v1/codex/superset/status     — reachability probe
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from services import superset as svc

logger = logging.getLogger(__name__)
router = APIRouter()


def _err(exc: Exception, status: int = 502) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": str(exc)})


@router.get("/superset/status")
async def superset_status():
    """Health probe — returns {reachable: bool}."""
    reachable = await svc.health_check()
    return {"reachable": reachable, "url": svc.SUPERSET_URL}


@router.post("/superset/setup")
async def superset_setup():
    """Register the Trino database connection in Superset (idempotent)."""
    try:
        result = await svc.ensure_trino_db()
        return result
    except Exception as exc:
        logger.warning("superset_setup: %s", exc)
        return _err(exc)


@router.get("/superset/dashboards")
async def superset_dashboards(page: int = 0, page_size: int = 50):
    """List published Superset dashboards for the embed picker."""
    try:
        return await svc.list_dashboards(page=page, page_size=page_size)
    except Exception as exc:
        logger.warning("superset_dashboards: %s", exc)
        return _err(exc)


@router.get("/superset/token/{dashboard_id}")
async def superset_guest_token(
    dashboard_id: int,
    x_codex_user_id: Optional[str] = Header(default=None),
):
    """Issue a guest token for embedding dashboard {dashboard_id}.

    The token is forwarded to the browser so Superset can render the
    embedded dashboard without exposing admin credentials.
    """
    user_info = {"username": x_codex_user_id or "codex-viewer"}
    try:
        token = await svc.guest_token(dashboard_id, user_info=user_info)
        return {"token": token, "dashboard_id": dashboard_id}
    except Exception as exc:
        logger.warning("superset_guest_token %s: %s", dashboard_id, exc)
        return _err(exc)
