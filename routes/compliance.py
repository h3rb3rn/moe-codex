"""routes/compliance.py — Runtime security & compliance posture (Track D.3.3).

Tier 1 — Falco (bare metal): syscall tracing via eBPF
Tier 2 — Trivy (VM-compatible): container image CVE scanning via Docker socket

GET  /v1/codex/compliance/status         — combined health probe (auto-detects tier)
GET  /v1/codex/compliance/falco/events   — recent Falco runtime alerts
GET  /v1/codex/compliance/falco/summary  — aggregated Falco alert counts
GET  /v1/codex/compliance/scap/summary   — latest OpenSCAP scan result
POST /v1/codex/compliance/scan/trigger   — oscap scan (Tier 1) or Trivy scan (Tier 2)
GET  /v1/codex/compliance/trivy/summary  — latest Trivy scan result
POST /v1/codex/compliance/trivy/trigger  — trigger Trivy image scan
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
    """Return compliance tier availability.

    reachable=True when either Falco OR Trivy is available.
    tier: 'falco' | 'trivy' | 'none'
    """
    falco_up     = await svc.falco_health()
    trivy_avail  = svc.trivy_available()
    scap_avail   = svc.get_scan_summary()["available"]
    trivy_result = svc.get_trivy_summary()

    if falco_up:
        tier = "falco"
    elif trivy_avail:
        tier = "trivy"
    else:
        tier = "none"

    return {
        "reachable":       falco_up or trivy_avail,
        "tier":            tier,
        "falco_reachable": falco_up,
        "trivy_available": trivy_avail,
        "scap_available":  scap_avail,
        "trivy_scanned":   trivy_result.get("available", False),
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
    """Trigger a compliance scan. Auto-selects tier:
    - Tier 1 (Falco available): tries oscap first
    - Tier 2 (VM/no eBPF): falls back to Trivy image scan
    """
    falco_up = await svc.falco_health()
    if falco_up:
        result = svc.trigger_scan()
        if result.get("status") != "unavailable":
            return result
    # Fallback to Trivy
    return svc.trigger_trivy_scan()


@router.get("/compliance/trivy/summary")
async def trivy_summary():
    """Return the latest Trivy vulnerability scan summary."""
    return svc.get_trivy_summary()


@router.post("/compliance/trivy/trigger")
async def trivy_trigger(target: str = ""):
    """Trigger an on-demand Trivy image scan. Works on VMs without eBPF.

    target: Docker image name to scan (default: moe-codex-codex-api)
    """
    result = svc.trigger_trivy_scan(target=target)
    if result.get("status") == "unavailable":
        return JSONResponse(
            status_code=503,
            content={"error": result["message"],
                     "hint": "Mount /var/run/docker.sock into the codex-api container."},
        )
    return result
