"""routes/trino.py — Trino SQL federation endpoints.

GET  /v1/codex/trino/health           — Trino reachability
GET  /v1/codex/trino/catalogs         — list available catalogs
GET  /v1/codex/trino/schemas/{cat}    — list schemas in a catalog
GET  /v1/codex/trino/tables/{cat}/{schema} — list tables
POST /v1/codex/trino/query            — execute SQL
POST /v1/codex/trino/nl               — natural language → SQL → execute
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.trino import (
    health_check, execute_query, nl_to_sql,
    list_catalogs, list_schemas, list_tables,
    TRINO_URL, TRINO_ENABLED, TRINO_MAX_ROWS,
)

router = APIRouter(prefix="/v1/codex/trino")


@router.get("/health")
async def trino_health():
    ok = await health_check()
    return {"trino_reachable": ok, "trino_enabled": TRINO_ENABLED, "trino_url": TRINO_URL}


@router.get("/catalogs")
async def trino_catalogs():
    catalogs = await list_catalogs()
    return {"catalogs": catalogs}


@router.get("/schemas/{catalog}")
async def trino_schemas(catalog: str):
    schemas = await list_schemas(catalog)
    return {"catalog": catalog, "schemas": schemas}


@router.get("/tables/{catalog}/{schema}")
async def trino_tables(catalog: str, schema: str):
    tables = await list_tables(catalog, schema)
    return {"catalog": catalog, "schema": schema, "tables": tables}


@router.post("/query")
async def trino_query(body: dict):
    """Execute a SQL query against Trino.

    Body: { "sql": "SELECT ...", "max_rows": 500 }
    """
    sql = (body.get("sql") or "").strip()
    if not sql:
        return JSONResponse(status_code=400, content={"error": "sql is required"})

    # Safety: block DDL that could drop data (read-only API by default).
    # Split on whitespace so tabs/newlines don't bypass the keyword check.
    _first_token = (sql.split() or [""])[0].upper()
    if _first_token in ("DROP", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "ALTER"):
        return JSONResponse(status_code=403, content={
            "error": "Write queries are not allowed via this endpoint. Use the Trino CLI for DDL."
        })

    max_rows = int(body.get("max_rows", TRINO_MAX_ROWS))
    result   = await execute_query(sql, max_rows=max_rows)

    if "error" in result:
        return JSONResponse(status_code=502, content=result)
    return result


@router.post("/nl")
async def trino_nl(body: dict):
    """Translate a natural-language question to SQL and execute it.

    Body: {
        "question": "How many entities were imported last week?",
        "schema_hint": "optional DDL or table list",
        "max_rows": 100,
        "dry_run": false   -- if true, return SQL without executing
    }
    """
    question = (body.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "question is required"})

    schema_hint = body.get("schema_hint", "")
    dry_run     = bool(body.get("dry_run", False))
    max_rows    = int(body.get("max_rows", TRINO_MAX_ROWS))

    try:
        sql = await nl_to_sql(question, schema_hint=schema_hint)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"NL→SQL translation failed: {exc}"})

    if dry_run:
        return {"question": question, "sql": sql, "executed": False}

    result = await execute_query(sql, max_rows=max_rows)
    if "error" in result:
        return JSONResponse(status_code=502, content={"sql": sql, **result})

    return {"question": question, "sql": sql, "executed": True, **result}
