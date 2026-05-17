"""routes/timeseries.py — TimescaleDB time-series catalog API (Track D.4.2).

GET  /v1/codex/timeseries/status           — reachability probe
GET  /v1/codex/timeseries/tables           — list hypertables
GET  /v1/codex/timeseries/query            — query a metric table
POST /v1/codex/timeseries/ingest           — write an event record
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services import timeseries as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/timeseries/status")
async def timeseries_status():
    reachable = await svc.health_check()
    return {"reachable": reachable}


@router.get("/timeseries/tables")
async def timeseries_tables():
    try:
        tables = await svc.list_hypertables()
        return {"tables": tables, "count": len(tables)}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.get("/timeseries/query")
async def timeseries_query(
    table:        str = Query(..., description="Hypertable name"),
    time_column:  str = Query(default="time"),
    value_column: str = Query(default="value"),
    label_column: str = Query(default="metric"),
    label:        Optional[str] = Query(default=None),
    window:       str = Query(default="7d", pattern="^(1d|7d|30d|90d)$"),
    limit:        int = Query(default=1000, ge=1, le=10000),
):
    """Return time-series data for a hypertable column."""
    result = await svc.query_metric(
        table=table,
        time_column=time_column,
        value_column=value_column,
        label_column=label_column,
        label_filter=label,
        window=window,
        limit=limit,
    )
    if "error" in result:
        return JSONResponse(status_code=502, content=result)
    return result


class IngestRequest(BaseModel):
    table:  str
    record: dict[str, Any]


@router.post("/timeseries/ingest")
async def timeseries_ingest(body: IngestRequest):
    """Write a single event record into a TimescaleDB hypertable."""
    ok = await svc.ingest_event(body.table, body.record)
    if not ok:
        return JSONResponse(status_code=502, content={"error": "Ingest failed"})
    return {"status": "ok"}
