"""routes/kestra.py — Kestra pipeline builder API (Phase D.2.1).

Exposes flows and executions from the Kestra orchestrator.
The admin UI uses these endpoints to list, trigger, and monitor pipelines.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services import kestra as svc

logger = logging.getLogger(__name__)
router = APIRouter()


def _unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "Kestra not available"})


@router.get("/kestra/flows")
async def kestra_flows(namespace: str = "", page: int = 1, size: int = 50):
    """List all Kestra flows, optionally filtered by namespace."""
    if not svc.KESTRA_ENABLED:
        return _unavailable()
    try:
        return await svc.list_flows(namespace=namespace, page=page, size=size)
    except Exception as exc:
        logger.warning("kestra_flows: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/kestra/flows/{namespace}/{flow_id}")
async def kestra_flow_detail(namespace: str, flow_id: str):
    """Return full YAML and metadata for a single flow."""
    if not svc.KESTRA_ENABLED:
        return _unavailable()
    try:
        return await svc.get_flow(namespace, flow_id)
    except Exception as exc:
        logger.warning("kestra_flow_detail: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


class TriggerRequest(BaseModel):
    namespace: str
    flow_id:   str
    inputs:    dict = {}


@router.post("/kestra/trigger")
async def kestra_trigger(body: TriggerRequest):
    """Trigger a Kestra flow execution."""
    if not svc.KESTRA_ENABLED:
        return _unavailable()
    try:
        result = await svc.trigger_flow(body.namespace, body.flow_id, body.inputs)
        return result
    except Exception as exc:
        logger.warning("kestra_trigger: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/kestra/executions")
async def kestra_executions(namespace: str = "", flow_id: str = "",
                            page: int = 1, size: int = 50):
    """List recent Kestra executions."""
    if not svc.KESTRA_ENABLED:
        return _unavailable()
    try:
        return await svc.list_executions(namespace=namespace, flow_id=flow_id,
                                         page=page, size=size)
    except Exception as exc:
        logger.warning("kestra_executions: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/kestra/executions/{execution_id}")
async def kestra_execution_detail(execution_id: str):
    """Return status and logs for a single execution."""
    if not svc.KESTRA_ENABLED:
        return _unavailable()
    try:
        return await svc.get_execution(execution_id)
    except Exception as exc:
        logger.warning("kestra_execution_detail: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/kestra/status")
async def kestra_status():
    """Health probe — returns {enabled, reachable}."""
    reachable = await svc.health_check() if svc.KESTRA_ENABLED else False
    return {"enabled": svc.KESTRA_ENABLED, "reachable": reachable}
