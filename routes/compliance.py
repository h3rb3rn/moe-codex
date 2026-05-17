"""routes/compliance.py — Runtime security & compliance posture (Track D.3.3).

GET  /v1/codex/compliance/falco/events   — recent Falco runtime alerts
GET  /v1/codex/compliance/falco/summary  — aggregated alert counts
GET  /v1/codex/compliance/scap/summary   — latest OpenSCAP scan result
POST /v1/codex/compliance/scan/trigger   — start an on-demand oscap scan
GET  /v1/codex/compliance/status         — combined health probe
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services import compliance as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/compliance/status")
async def compliance_status():
    """Return reachability of Falco and OpenSCAP result availability."""
    falco_up   = await svc.falco_health()
    scap_avail = svc.get_scan_summary()["available"]
    return {
        "falco_reachable": falco_up,
        "scap_available":  scap_avail,
    }


@router.get("/compliance/falco/events")
async def falco_events(limit: int = Query(default=100, ge=1, le=500)):
    """Return the most recent Falco runtime alerts."""
    events = svc.read_falco_events(limit=limit)
    return {"events": events, "count": len(events)}


@router.get("/compliance/falco/summary")
async def falco_summary(limit: int = Query(default=500, ge=1, le=2000)):
    """Return aggregated Falco alert counts by priority and top-rules."""
    events  = svc.read_falco_events(limit=limit)
    summary = svc.falco_summary(events)
    return summary


@router.get("/compliance/scap/summary")
async def scap_summary():
    """Return the latest OpenSCAP scan result summary."""
    return svc.get_scan_summary()


@router.post("/compliance/scan/trigger")
async def scan_trigger():
    """Trigger an on-demand oscap scan (requires oscap binary on host)."""
    result = svc.trigger_scan()
    if result.get("status") == "unavailable":
        return JSONResponse(
            status_code=503,
            content={"error": result["message"],
                     "hint": "Install openscap-scanner or trigger via a Kestra workflow."},
        )
    return result
