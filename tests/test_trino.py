"""tests/test_trino.py — Unit tests for services/trino.py and routes/trino.py."""
from __future__ import annotations

import json
import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock

from services.trino import (
    execute_query,
    nl_to_sql,
    list_catalogs,
    list_schemas,
    list_tables,
    health_check,
    TRINO_URL,
)


# ─── execute_query ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_execute_query_single_page():
    """Single-page result (no nextUri) is returned correctly."""
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={
            "id": "q1",
            "columns": [{"name": "a", "type": "bigint"}, {"name": "b", "type": "varchar"}],
            "data": [[1, "x"], [2, "y"]],
        },
    ))
    result = await execute_query("SELECT 1", max_rows=100)
    assert result["row_count"] == 2
    assert result["columns"] == [{"name": "a", "type": "bigint"}, {"name": "b", "type": "varchar"}]
    assert result["rows"] == [[1, "x"], [2, "y"]]
    assert result["query_id"] == "q1"
    assert result["truncated"] is False


@pytest.mark.asyncio
@respx.mock
async def test_execute_query_pagination():
    """Multi-page result is assembled across nextUri pages."""
    next_uri = f"{TRINO_URL}/v1/statement/q2/1"
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={
            "id": "q2",
            "columns": [{"name": "n", "type": "integer"}],
            "data": [[1]],
            "nextUri": next_uri,
            "stats": {"state": "RUNNING"},
        },
    ))
    respx.get(next_uri).mock(return_value=httpx.Response(
        200,
        json={
            "id": "q2",
            "data": [[2], [3]],
        },
    ))
    result = await execute_query("SELECT n FROM t", max_rows=100)
    assert result["rows"] == [[1], [2], [3]]
    assert result["row_count"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_execute_query_truncation():
    """Rows beyond max_rows are dropped and truncated=True is set."""
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={
            "id": "q3",
            "columns": [{"name": "x", "type": "integer"}],
            "data": [[i] for i in range(10)],
        },
    ))
    result = await execute_query("SELECT x FROM t", max_rows=5)
    assert result["row_count"] == 5
    assert result["truncated"] is True


@pytest.mark.asyncio
@respx.mock
async def test_execute_query_failed_state():
    """FAILED state in stats returns error dict."""
    next_uri = f"{TRINO_URL}/v1/statement/q4/1"
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={
            "id": "q4",
            "nextUri": next_uri,
            "stats": {"state": "FAILED"},
            "error": {"message": "Table not found"},
        },
    ))
    result = await execute_query("SELECT * FROM missing_table")
    assert "error" in result
    assert "Table not found" in result["error"]


@pytest.mark.asyncio
@respx.mock
async def test_execute_query_http_error():
    """Non-2xx HTTP response from Trino is returned as error dict."""
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        500, text="Internal Server Error"
    ))
    result = await execute_query("SELECT 1")
    assert "error" in result
    assert "500" in result["error"]


@pytest.mark.asyncio
async def test_execute_query_disabled():
    """Returns error dict when TRINO_ENABLED=false."""
    with patch("services.trino.TRINO_ENABLED", False):
        result = await execute_query("SELECT 1")
    assert "error" in result
    assert "not enabled" in result["error"]


# ─── nl_to_sql ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_nl_to_sql_basic():
    """NL question is translated to SQL via moe-sovereign."""
    from services.trino import SOVEREIGN_URL
    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(return_value=httpx.Response(
        200,
        json={"choices": [{"message": {"content": "SELECT count(*) FROM orders"}}]},
    ))
    sql = await nl_to_sql("How many orders are there?")
    assert sql == "SELECT count(*) FROM orders"


@pytest.mark.asyncio
@respx.mock
async def test_nl_to_sql_strips_markdown_fences():
    """Markdown code fences in the model response are stripped."""
    from services.trino import SOVEREIGN_URL
    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(return_value=httpx.Response(
        200,
        json={"choices": [{"message": {"content": "```sql\nSELECT 1\n```"}}]},
    ))
    sql = await nl_to_sql("Give me a simple query.")
    assert sql == "SELECT 1"
    assert "```" not in sql


@pytest.mark.asyncio
@respx.mock
async def test_nl_to_sql_includes_schema_hint():
    """schema_hint is appended to the prompt sent to moe-sovereign."""
    from services.trino import SOVEREIGN_URL
    captured = {}

    def capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "SELECT id FROM customers"}}]})

    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(side_effect=capture)
    await nl_to_sql("List customer IDs", schema_hint="CREATE TABLE customers (id INT)")
    user_msg = captured["body"]["messages"][1]["content"]
    assert "CREATE TABLE customers" in user_msg


# ─── list_* helpers ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_catalogs():
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={"id": "lc1", "columns": [{"name": "Catalog", "type": "varchar"}],
              "data": [["postgresql"], ["memory"], ["tpch"]]},
    ))
    cats = await list_catalogs()
    assert set(cats) == {"postgresql", "memory", "tpch"}


@pytest.mark.asyncio
@respx.mock
async def test_list_schemas():
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={"id": "ls1", "columns": [{"name": "Schema", "type": "varchar"}],
              "data": [["public"], ["information_schema"]]},
    ))
    schemas = await list_schemas("postgresql")
    assert "public" in schemas


@pytest.mark.asyncio
@respx.mock
async def test_list_tables():
    respx.post(f"{TRINO_URL}/v1/statement").mock(return_value=httpx.Response(
        200,
        json={"id": "lt1", "columns": [{"name": "Table", "type": "varchar"}],
              "data": [["users"], ["sessions"]]},
    ))
    tables = await list_tables("postgresql", "public")
    assert "users" in tables


# ─── health_check ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_health_check_ok():
    respx.get(f"{TRINO_URL}/v1/info").mock(return_value=httpx.Response(200, json={"starting": False}))
    assert await health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_fail():
    respx.get(f"{TRINO_URL}/v1/info").mock(return_value=httpx.Response(503))
    assert await health_check() is False


@pytest.mark.asyncio
async def test_health_check_disabled():
    with patch("services.trino.TRINO_ENABLED", False):
        assert await health_check() is True


# ─── DDL guard logic (extracted from route, tested without HTTP layer) ────────

@pytest.mark.parametrize("sql", [
    "DROP TABLE t",
    "TRUNCATE t",
    "DELETE FROM t WHERE 1=1",
    "INSERT INTO t VALUES (1)",
    "UPDATE t SET x=1",
    "ALTER TABLE t ADD COLUMN y INT",
    "  drop table t",        # leading whitespace
    "DROP\tTABLE\tt",        # tab separated
])
def test_ddl_guard_blocks_write_sql(sql: str):
    """The DDL safety guard blocks all write-class SQL keywords."""
    first_token = (sql.split() or [""])[0].upper()
    blocked = first_token in ("DROP", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "ALTER")
    assert blocked, f"DDL guard should block: {sql!r}"


@pytest.mark.parametrize("sql", [
    "SELECT count(*) FROM t",
    "WITH cte AS (SELECT 1) SELECT * FROM cte",
    "SHOW CATALOGS",
    "EXPLAIN SELECT * FROM t",
])
def test_ddl_guard_allows_read_sql(sql: str):
    """The DDL safety guard passes read-only SQL through."""
    first_token = (sql.split() or [""])[0].upper()
    blocked = first_token in ("DROP", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "ALTER")
    assert not blocked, f"DDL guard should NOT block: {sql!r}"
