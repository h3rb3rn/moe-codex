"""routes/dossier.py — Case file / investigation container (Track D.5).

GET  /v1/codex/dossier/list              — list all dossiers
POST /v1/codex/dossier/create            — create a new dossier
GET  /v1/codex/dossier/{id}              — get dossier with all pinned items
POST /v1/codex/dossier/{id}/pin          — pin an evidence item
DELETE /v1/codex/dossier/{id}/pin/{item} — unpin an item
DELETE /v1/codex/dossier/{id}            — delete dossier
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import state
from services import dossier as svc

logger = logging.getLogger(__name__)
router = APIRouter()


def _no_redis():
    return JSONResponse(
        status_code=503,
        content={"error": "Redis not available — dossiers require Redis/Valkey"},
    )


class CreateRequest(BaseModel):
    title:       str
    description: Optional[str] = ""
    created_by:  Optional[str] = ""


class PinRequest(BaseModel):
    module: str   # graph | timeline | document | note | geo | compliance
    kind:   str   # entity | run | feature | alert | commit | ...
    ref_id: str
    label:  str
    note:   Optional[str] = ""


@router.get("/dossier/list")
async def dossier_list(limit: int = 50):
    if state.redis_client is None:
        return _no_redis()
    return {"dossiers": await svc.list_all(state.redis_client, limit=limit)}


@router.post("/dossier/create")
async def dossier_create(body: CreateRequest):
    if state.redis_client is None:
        return _no_redis()
    result = await svc.create(
        state.redis_client,
        title=body.title,
        description=body.description or "",
        created_by=body.created_by or "",
    )
    if "error" in result:
        return JSONResponse(status_code=503, content=result)
    return result


@router.get("/dossier/{dossier_id}")
async def dossier_get(dossier_id: str):
    if state.redis_client is None:
        return _no_redis()
    d = await svc.get(state.redis_client, dossier_id)
    if d is None:
        return JSONResponse(status_code=404, content={"error": "Dossier not found"})
    return d


@router.post("/dossier/{dossier_id}/pin")
async def dossier_pin(dossier_id: str, body: PinRequest):
    if state.redis_client is None:
        return _no_redis()
    item = await svc.pin_item(
        state.redis_client, dossier_id,
        module=body.module, kind=body.kind,
        ref_id=body.ref_id, label=body.label,
        note=body.note or "",
    )
    if item is None:
        return JSONResponse(status_code=404, content={"error": "Dossier not found"})
    return item


@router.delete("/dossier/{dossier_id}/pin/{item_id}")
async def dossier_unpin(dossier_id: str, item_id: str):
    if state.redis_client is None:
        return _no_redis()
    ok = await svc.unpin_item(state.redis_client, dossier_id, item_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    return {"status": "removed", "item_id": item_id}


@router.delete("/dossier/{dossier_id}")
async def dossier_delete(dossier_id: str):
    if state.redis_client is None:
        return _no_redis()
    ok = await svc.delete(state.redis_client, dossier_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Dossier not found"})
    return {"status": "deleted", "id": dossier_id}
