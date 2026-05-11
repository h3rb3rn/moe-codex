"""Data Health drift events (Phase 23)."""
from __future__ import annotations

from fastapi import APIRouter

import state
from services.data_health import recent_events

router = APIRouter()


@router.get("/health/events")
async def health_events(limit: int = 50):
    """Recent drift events, newest first. Cap 500 per Redis ringbuffer."""
    if state.redis_client is None:
        return {"events": [], "count": 0, "status": "redis_unavailable"}
    events = await recent_events(state.redis_client, limit=limit)
    return {"events": events, "count": len(events), "status": "ok"}
