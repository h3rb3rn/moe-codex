"""services/trino.py — Trino SQL federation client.

Executes SQL queries across federated catalogs (PostgreSQL, memory, tpch)
via Trino's HTTP API. Optionally translates natural-language questions to
SQL using moe-sovereign before executing.

Trino HTTP API:
  POST /v1/statement          — submit query, returns first page + nextUri
  GET  <nextUri>              — fetch next result page
  DELETE <nextUri>            — cancel query
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TRINO_URL        = os.getenv("TRINO_URL", "http://moe-trino:8080")
TRINO_USER       = os.getenv("TRINO_USER", "codex")
TRINO_CATALOG    = os.getenv("TRINO_CATALOG", "postgresql")
TRINO_SCHEMA     = os.getenv("TRINO_SCHEMA", "public")
TRINO_ENABLED    = os.getenv("TRINO_ENABLED", "true").lower() not in ("0", "false", "no")
TRINO_TIMEOUT    = float(os.getenv("TRINO_TIMEOUT", "60"))
TRINO_MAX_ROWS   = int(os.getenv("TRINO_MAX_ROWS", "1000"))

SOVEREIGN_URL     = os.getenv("SOVEREIGN_URL", "http://moe-sovereign:8002")
SOVEREIGN_API_KEY = os.getenv("SOVEREIGN_API_KEY", "")

_NL_TO_SQL_SYSTEM = (
    "You are a SQL expert. Convert the user's natural language question into "
    "a valid Trino SQL query. Available catalogs: postgresql (schema: public), "
    "memory, tpch. Return ONLY the SQL query — no explanation, no markdown fences."
)


def _trino_headers() -> dict[str, str]:
    return {
        "X-Trino-User":    TRINO_USER,
        "X-Trino-Catalog": TRINO_CATALOG,
        "X-Trino-Schema":  TRINO_SCHEMA,
        "Content-Type":    "text/plain",
    }


async def execute_query(sql: str, max_rows: int = TRINO_MAX_ROWS) -> dict[str, Any]:
    """Execute a SQL query against Trino and return all result rows.

    Returns:
        {
            "columns": [{"name": ..., "type": ...}, ...],
            "rows":    [[val, ...], ...],
            "row_count": int,
            "query_id": str,
            "elapsed_ms": int,
        }
    """
    if not TRINO_ENABLED:
        return {"error": "Trino is not enabled (TRINO_ENABLED=false)"}

    t0 = time.monotonic()
    columns: list[dict] = []
    rows: list[list] = []
    query_id = ""

    try:
        async with httpx.AsyncClient(timeout=TRINO_TIMEOUT) as client:
            # Submit query
            resp = await client.post(
                f"{TRINO_URL}/v1/statement",
                content=sql,
                headers=_trino_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            query_id = data.get("id", "")

            # Page through results
            while True:
                if "columns" in data and not columns:
                    columns = [{"name": c["name"], "type": c["type"]} for c in data["columns"]]
                for row in data.get("data", []):
                    if len(rows) < max_rows:
                        rows.append(row)

                next_uri = data.get("nextUri")
                if not next_uri:
                    break

                state = data.get("stats", {}).get("state", "")
                if state in ("FAILED",):
                    error = data.get("error", {})
                    return {
                        "error":    error.get("message", "Query failed"),
                        "query_id": query_id,
                    }

                resp = await client.get(next_uri, headers=_trino_headers())
                resp.raise_for_status()
                data = resp.json()

    except httpx.HTTPStatusError as exc:
        return {"error": f"Trino HTTP {exc.response.status_code}: {exc.response.text[:500]}"}
    except Exception as exc:
        return {"error": str(exc)}

    return {
        "columns":    columns,
        "rows":       rows,
        "row_count":  len(rows),
        "query_id":   query_id,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "truncated":  len(rows) >= max_rows,
    }


async def nl_to_sql(question: str, schema_hint: str = "") -> str:
    """Translate a natural-language question to SQL via moe-sovereign.

    schema_hint: optional DDL or table list to inject into the prompt.
    Returns the SQL string, or raises on failure.
    """
    context = f"\n\nAvailable schema hint:\n{schema_hint}" if schema_hint else ""
    prompt  = f"{question}{context}"
    headers = {"Content-Type": "application/json"}
    if SOVEREIGN_API_KEY:
        headers["Authorization"] = f"Bearer {SOVEREIGN_API_KEY}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{SOVEREIGN_URL}/v1/chat/completions",
            json={
                "model":    "data_analyst",
                "messages": [
                    {"role": "system", "content": _NL_TO_SQL_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 512,
            },
            headers=headers,
        )
        r.raise_for_status()
        sql = r.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if model added them anyway
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return sql


async def list_catalogs() -> list[str]:
    result = await execute_query("SHOW CATALOGS", max_rows=50)
    if "error" in result:
        return []
    return [row[0] for row in result.get("rows", [])]


async def list_schemas(catalog: str) -> list[str]:
    result = await execute_query(f"SHOW SCHEMAS FROM {catalog}", max_rows=100)
    if "error" in result:
        return []
    return [row[0] for row in result.get("rows", [])]


async def list_tables(catalog: str, schema: str) -> list[str]:
    result = await execute_query(f"SHOW TABLES FROM {catalog}.{schema}", max_rows=500)
    if "error" in result:
        return []
    return [row[0] for row in result.get("rows", [])]


async def health_check() -> bool:
    if not TRINO_ENABLED:
        return True
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{TRINO_URL}/v1/info")
            return r.status_code == 200
    except Exception:
        return False
