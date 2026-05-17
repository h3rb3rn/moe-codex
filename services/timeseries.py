"""services/timeseries.py — TimescaleDB time-series catalog client (Track D.4.2).

Connects moe-codex to TimescaleDB (PostgreSQL + timescaledb extension) to provide:
  1. Hypertable listing — datasets stored as time-series.
  2. Metric query — return recent data for a given metric key.
  3. Schema introspection — column names and time-column detection.
  4. Ingest — write an event record (used by health drift + Kestra callbacks).

Uses asyncpg directly to avoid heavy ORM overhead; all queries are read-only
except `ingest_event`. The TimescaleDB instance is dedicated to codex — it does
not share data with moe-sovereign's terra_checkpoints Postgres.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Primary connection via the REST-over-HTTP facade (httpx to PostgREST sidecar).
# If TIMESERIES_PGREST_URL is set we use PostgREST; otherwise we fall back to
# direct asyncpg (requires asyncpg in requirements).
TIMESERIES_PGREST_URL = os.getenv("TIMESERIES_PGREST_URL", "http://moe-timescale-rest:3000")
TIMESERIES_DB_URL     = os.getenv("TIMESERIES_DB_URL", "")  # postgresql://user:pass@host/db
TIMESERIES_TIMEOUT    = float(os.getenv("TIMESERIES_TIMEOUT", "10"))
TIMESERIES_SCHEMA     = os.getenv("TIMESERIES_SCHEMA", "codex")


async def health_check() -> bool:
    """Check TimescaleDB reachability via PostgREST /health."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{TIMESERIES_PGREST_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


async def list_hypertables() -> list[dict[str, Any]]:
    """Return all hypertables (time-series tables) in the codex schema."""
    try:
        async with httpx.AsyncClient(timeout=TIMESERIES_TIMEOUT) as c:
            r = await c.get(
                f"{TIMESERIES_PGREST_URL}/timescaledb_information.hypertables",
                params={"schema_name": f"eq.{TIMESERIES_SCHEMA}"},
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                return r.json()
            return []
    except Exception as exc:
        logger.debug("list_hypertables: %s", exc)
        return []


async def query_metric(
    table: str,
    time_column: str = "time",
    value_column: str = "value",
    label_column: str = "metric",
    label_filter: str | None = None,
    window: str = "7d",
    limit: int = 1000,
) -> dict[str, Any]:
    """Return time-series data for a metric from a hypertable.

    Returns {columns: [...], rows: [[ts, val], ...], total: int}
    """
    window_map = {"1d": "1 day", "7d": "7 days", "30d": "30 days", "90d": "90 days"}
    interval   = window_map.get(window, "7 days")

    # Use PostgREST horizontal filtering
    params: dict[str, str] = {
        f"{time_column}": f"gte.now()-interval '{interval}'",
        "order":  f"{time_column}.asc",
        "limit":  str(limit),
        "select": f"{time_column},{value_column}" + (f",{label_column}" if label_column else ""),
    }
    if label_filter:
        params[label_column] = f"eq.{label_filter}"

    try:
        async with httpx.AsyncClient(timeout=TIMESERIES_TIMEOUT) as c:
            r = await c.get(
                f"{TIMESERIES_PGREST_URL}/{TIMESERIES_SCHEMA}.{table}",
                params=params,
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                rows = r.json()
                return {
                    "table":   table,
                    "window":  window,
                    "columns": [time_column, value_column],
                    "rows":    [[row.get(time_column), row.get(value_column)] for row in rows],
                    "total":   len(rows),
                }
            return {"table": table, "error": f"HTTP {r.status_code}", "rows": [], "total": 0}
    except Exception as exc:
        logger.debug("query_metric: %s", exc)
        return {"table": table, "error": str(exc), "rows": [], "total": 0}


async def ingest_event(table: str, record: dict[str, Any]) -> bool:
    """Write a single event record into a TimescaleDB hypertable."""
    try:
        async with httpx.AsyncClient(timeout=TIMESERIES_TIMEOUT) as c:
            r = await c.post(
                f"{TIMESERIES_PGREST_URL}/{TIMESERIES_SCHEMA}.{table}",
                json=record,
                headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
            )
            return r.status_code in (200, 201, 204)
    except Exception as exc:
        logger.debug("ingest_event: %s", exc)
        return False


async def get_schema(table: str) -> list[dict[str, Any]]:
    """Return column definitions for a table."""
    try:
        async with httpx.AsyncClient(timeout=TIMESERIES_TIMEOUT) as c:
            r = await c.get(
                f"{TIMESERIES_PGREST_URL}/{TIMESERIES_SCHEMA}.{table}",
                params={"limit": "0"},
                headers={"Accept": "application/openapi+json"},
            )
            if r.status_code == 200:
                return r.json()
            return []
    except Exception as exc:
        logger.debug("get_schema: %s", exc)
        return []
