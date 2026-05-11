"""ETL Fan-Out (NiFi proxy, Phase 17)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.etl_pipeline import (
    submit_to_pipeline,
    get_system_diagnostics,
    summarise_diagnostics,
    _submit_enabled,
)

router = APIRouter()


@router.post("/etl/submit")
async def etl_submit(raw_request: Request):
    """Forward a payload to the NiFi ListenHTTP processor."""
    if not _submit_enabled():
        return JSONResponse(status_code=503, content={"error": "NIFI_INGEST_URL not set"})
    try:
        payload = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    result = await submit_to_pipeline(payload)
    if not result:
        return JSONResponse(status_code=502, content={"error": "NiFi submission failed"})
    return {"status": "ok", "nifi": result}


@router.get("/etl/status")
async def etl_status():
    """Lightweight NiFi system diagnostics."""
    diag = await get_system_diagnostics()
    return summarise_diagnostics(diag)
