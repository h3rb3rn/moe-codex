"""routes/notes.py — HedgeDoc collaborative notes proxy (Track D.4.3).

GET  /v1/codex/notes/status              — reachability probe
GET  /v1/codex/notes/list                — list recent notes
POST /v1/codex/notes/create              — create a new note
GET  /v1/codex/notes/{note_id}/content   — raw Markdown content
GET  /v1/codex/notes/{note_id}/embed     — embed URL
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from services import hedgedoc as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/notes/status")
async def notes_status():
    reachable = await svc.health_check()
    return {"reachable": reachable, "url": svc.HEDGEDOC_URL}


@router.get("/notes/list")
async def notes_list(limit: int = 50):
    notes = await svc.list_notes(limit=limit)
    return {"notes": notes, "count": len(notes)}


class CreateNoteRequest(BaseModel):
    title:   str
    content: Optional[str] = ""


@router.post("/notes/create")
async def notes_create(body: CreateNoteRequest):
    result = await svc.create_note(body.title, body.content or "")
    if "error" in result:
        return JSONResponse(status_code=502, content=result)
    return result


@router.get("/notes/{note_id}/content", response_class=PlainTextResponse)
async def notes_content(note_id: str):
    content = await svc.get_note(note_id)
    return PlainTextResponse(content=content or "")


@router.get("/notes/{note_id}/embed")
async def notes_embed(note_id: str, read_only: bool = True):
    return {"embed_url": svc.embed_url(note_id, read_only=read_only), "note_id": note_id}
