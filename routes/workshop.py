"""routes/workshop.py — Budibase low-code app builder proxy (Track D.4.1).

GET  /v1/codex/workshop/status        — Budibase reachability probe
GET  /v1/codex/workshop/apps          — list published apps
GET  /v1/codex/workshop/apps/{app_id} — single app metadata
GET  /v1/codex/workshop/embed/{app_id} — embed URL for iframe
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services import budibase as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/workshop/status")
async def workshop_status():
    reachable = await svc.health_check()
    return {"reachable": reachable, "url": svc.BUDIBASE_URL}


@router.get("/workshop/apps")
async def workshop_apps(page: int = 1, per_page: int = 50):
    try:
        return await svc.list_apps(page=page, per_page=per_page)
    except Exception as exc:
        logger.warning("workshop_apps: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/workshop/apps/{app_id}")
async def workshop_app_detail(app_id: str):
    try:
        return await svc.get_app(app_id)
    except Exception as exc:
        logger.warning("workshop_app_detail %s: %s", app_id, exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/workshop/embed/{app_id}")
async def workshop_embed_url(app_id: str):
    url = await svc.app_embed_url(app_id)
    return {"embed_url": url, "app_id": app_id}
