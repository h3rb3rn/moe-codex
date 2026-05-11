"""routes/guardrails.py — NeMo Guardrails management endpoints.

GET  /v1/codex/guardrails/config         — return active guardrails config
POST /v1/codex/guardrails/reload         — hot-reload config from disk
POST /v1/codex/guardrails/check/input    — test a text against input rails
POST /v1/codex/guardrails/check/output   — test a text against output rails
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.guardrails import (
    get_config, reload_config,
    check_input, check_output,
    GUARDRAILS_DIR, GUARDRAILS_ENABLED,
)

router = APIRouter(prefix="/v1/codex/guardrails")


@router.get("/config")
async def guardrails_config():
    return {
        "enabled":       GUARDRAILS_ENABLED,
        "guardrails_dir": str(GUARDRAILS_DIR),
        "config":        get_config(),
    }


@router.post("/reload")
async def guardrails_reload():
    config = reload_config()
    patterns = config.get("patterns", {})
    rails    = config.get("rails", {})
    return {
        "status":          "reloaded",
        "input_flows":     rails.get("input", {}).get("flows", []),
        "output_flows":    rails.get("output", {}).get("flows", []),
        "pattern_count":   len(patterns),
    }


@router.post("/check/input")
async def guardrails_check_input(body: dict):
    """Test a text string against the configured input rails.

    Body: { "text": "..." }
    Returns: { "blocked": bool, "violations": [...] }
    """
    text = body.get("text", "")
    if not text:
        return JSONResponse(status_code=400, content={"error": "text is required"})
    violations = await check_input(text)
    return {"blocked": len(violations) > 0, "violations": violations}


@router.post("/check/output")
async def guardrails_check_output(body: dict):
    """Test a text string against the configured output rails.

    Body: { "text": "..." }
    Returns: { "blocked": bool, "violations": [...] }
    """
    text = body.get("text", "")
    if not text:
        return JSONResponse(status_code=400, content={"error": "text is required"})
    violations = await check_output(text)
    return {"blocked": len(violations) > 0, "violations": violations}
