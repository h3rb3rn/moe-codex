"""routes/opa.py — OPA policy management endpoints.

GET  /v1/codex/opa/health   — check if OPA is reachable
POST /v1/codex/opa/evaluate — ad-hoc policy evaluation for testing
GET  /v1/codex/opa/config   — return current OPA config (enabled, fail_open, url)
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.opa import (
    health_check, evaluate,
    OPA_URL, OPA_ENABLED, OPA_FAIL_OPEN,
    _extract_user,
)

router = APIRouter(prefix="/v1/codex/opa")


@router.get("/health")
async def opa_health():
    ok = await health_check()
    return {"opa_reachable": ok, "opa_enabled": OPA_ENABLED}


@router.get("/config")
async def opa_config():
    return {
        "opa_enabled":   OPA_ENABLED,
        "opa_fail_open": OPA_FAIL_OPEN,
        "opa_url":       OPA_URL,
    }


@router.post("/evaluate")
async def opa_evaluate(raw_request: Request):
    """Ad-hoc policy evaluation — for testing and Admin UI policy explorer.

    Body: { "package": "codex.catalog", "rule": "allow", "input": {...} }
    """
    try:
        body = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    package = body.get("package", "")
    rule    = body.get("rule", "allow")
    inp     = body.get("input", {})

    if not package:
        return JSONResponse(status_code=400, content={"error": "package is required"})

    result = await evaluate(package, rule, inp)
    return {"package": package, "rule": rule, "result": result, "input": inp}


@router.post("/check/catalog")
async def opa_check_catalog(raw_request: Request):
    """Convenience endpoint: check catalog access for the calling user.

    Body: { "dataset": { "name": "...", "classification": "INTERNAL", "owner_group": "..." }, "action": "read" }
    """
    from services.opa import catalog_allow
    try:
        body = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    user    = _extract_user(dict(raw_request.headers))
    dataset = body.get("dataset", {})
    action  = body.get("action", "read")
    allowed = await catalog_allow(user, dataset, action)
    return {"allowed": allowed, "user": user, "dataset": dataset, "action": action}


@router.post("/check/approval")
async def opa_check_approval(raw_request: Request):
    """Convenience endpoint: check approval action for the calling user.

    Body: { "action": "approve" }
    """
    from services.opa import approval_allow
    try:
        body = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    user    = _extract_user(dict(raw_request.headers))
    action  = body.get("action", "view")
    allowed = await approval_allow(user, action)
    return {"allowed": allowed, "user": user, "action": action}
