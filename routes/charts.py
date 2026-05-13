"""routes/charts.py — Chart Builder & Pivot Analysis (Phase D.2.3).

Runs parameterized SQL against Trino and returns structured data for
Chart.js / PivotTable.js rendering in the admin UI. When SUPERSET_URL is
configured the admin UI surfaces an "Open in Superset" deep-link.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

SUPERSET_URL = os.getenv("SUPERSET_URL", "")

# Curated built-in queries available as chart presets
_PRESET_QUERIES: list[dict[str, Any]] = [
    {
        "id":          "model_usage_daily",
        "title":       "Model usage — daily",
        "description": "Chat completions per model per day (last 30 days)",
        "sql": """
SELECT date_trunc('day', created_at) AS day,
       model,
       COUNT(*) AS requests,
       SUM(prompt_tokens + completion_tokens) AS total_tokens
FROM moe.requests
WHERE created_at >= NOW() - INTERVAL '30' DAY
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
""",
        "chart_type": "bar",
        "x_axis":     "day",
        "series":     "model",
        "y_axis":     "requests",
    },
    {
        "id":          "catalog_dataset_counts",
        "title":       "Catalog datasets by namespace",
        "description": "Dataset count per Marquez namespace",
        "sql": """
SELECT namespace, COUNT(*) AS dataset_count
FROM marquez.public.datasets
GROUP BY namespace
ORDER BY 2 DESC
""",
        "chart_type": "pie",
        "x_axis":     "namespace",
        "y_axis":     "dataset_count",
    },
    {
        "id":          "lineage_job_runs",
        "title":       "Lineage job runs — last 7 days",
        "description": "Run state distribution across all jobs",
        "sql": """
SELECT current_run_state AS state, COUNT(*) AS jobs
FROM marquez.public.jobs
GROUP BY current_run_state
ORDER BY 2 DESC
""",
        "chart_type": "doughnut",
        "x_axis":     "state",
        "y_axis":     "jobs",
    },
]


@router.get("/charts/presets")
async def chart_presets():
    """Return list of built-in chart presets."""
    return {
        "presets":      _PRESET_QUERIES,
        "superset_url": SUPERSET_URL,
    }


class ChartQueryRequest(BaseModel):
    sql:       str
    max_rows:  int = 500
    chart_type: str = "bar"
    x_axis:    str = ""
    series:    str = ""
    y_axis:    str = ""


@router.post("/charts/query")
async def chart_query(body: ChartQueryRequest):
    """Execute a SQL query via Trino and return data formatted for charting.

    Response: {columns, rows, chart_hint: {type, x, y, series}}
    """
    from services.trino import TRINO_ENABLED
    if not TRINO_ENABLED:
        return JSONResponse(status_code=503, content={"error": "Trino not available"})

    import httpx
    TRINO_SVC_URL = os.getenv("TRINO_URL", "http://moe-trino:8080")
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{TRINO_SVC_URL}/v1/statement",
                content=body.sql.strip(),
                headers={
                    "X-Trino-User":    "codex",
                    "X-Trino-Catalog": "hive",
                    "X-Trino-Schema":  "default",
                    "Content-Type":    "text/plain",
                },
            )
            r.raise_for_status()
            result = r.json()

            # Follow nextUri until data is complete
            columns: list[str] = []
            rows: list[list] = []
            for col in result.get("columns") or []:
                columns.append(col.get("name", ""))
            for row in result.get("data") or []:
                rows.append(row)

            next_uri = result.get("nextUri")
            while next_uri and len(rows) < body.max_rows:
                nr = await c.get(next_uri)
                nr.raise_for_status()
                ndata = nr.json()
                if not columns and ndata.get("columns"):
                    columns = [c.get("name", "") for c in ndata["columns"]]
                for row in ndata.get("data") or []:
                    rows.append(row)
                next_uri = ndata.get("nextUri")

        return {
            "columns":    columns,
            "rows":       rows[:body.max_rows],
            "row_count":  len(rows),
            "chart_hint": {
                "type":   body.chart_type,
                "x":      body.x_axis or (columns[0] if columns else ""),
                "y":      body.y_axis or (columns[-1] if len(columns) > 1 else ""),
                "series": body.series,
            },
        }
    except Exception as exc:
        logger.warning("chart_query: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})
