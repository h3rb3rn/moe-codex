"""Unit tests for D3 services: Superset, OpenSearch, Compliance.

All HTTP calls are mocked so no external services need to be running.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
import httpx

from services.superset import (
    health_check as superset_health,
    list_dashboards,
    guest_token,
    ensure_trino_db,
    SUPERSET_URL,
    SUPERSET_USER,
    SUPERSET_PASS,
)
from services.opensearch_client import (
    health_check as os_health,
    ensure_index,
    index_doc,
    bulk_index,
    search,
    get_index_stats,
    OPENSEARCH_URL,
    INDEX_NAME,
)
from services.compliance import (
    read_falco_events,
    falco_summary,
    get_scan_summary,
    _parse_falco_line,
    OPENSCAP_RESULTS_DIR,
)


# ─── Superset ─────────────────────────────────────────────────────────────────

_LOGIN_PAYLOAD = {"access_token": "tok123"}
_LOGIN_URL     = f"{SUPERSET_URL}/api/v1/security/login"


@pytest.mark.anyio
@respx.mock
async def test_superset_health_ok():
    respx.get(f"{SUPERSET_URL}/health").mock(
        return_value=httpx.Response(200, text="OK")
    )
    assert await superset_health() is True


@pytest.mark.anyio
@respx.mock
async def test_superset_health_down():
    respx.get(f"{SUPERSET_URL}/health").mock(
        return_value=httpx.Response(503, text="down")
    )
    assert await superset_health() is False


@pytest.mark.anyio
@respx.mock
async def test_superset_health_network_error():
    respx.get(f"{SUPERSET_URL}/health").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await superset_health() is False


@pytest.mark.anyio
@respx.mock
async def test_list_dashboards():
    respx.post(_LOGIN_URL).mock(return_value=httpx.Response(200, json=_LOGIN_PAYLOAD))
    respx.get(f"{SUPERSET_URL}/api/v1/dashboard/").mock(
        return_value=httpx.Response(200, json={
            "result": [{"id": 1, "dashboard_title": "Sales", "slug": "sales"}],
            "count": 1,
        })
    )
    result = await list_dashboards()
    assert result["count"] == 1
    assert result["result"][0]["dashboard_title"] == "Sales"


@pytest.mark.anyio
@respx.mock
async def test_guest_token():
    respx.post(_LOGIN_URL).mock(return_value=httpx.Response(200, json=_LOGIN_PAYLOAD))
    respx.post(f"{SUPERSET_URL}/api/v1/security/guest_token/").mock(
        return_value=httpx.Response(200, json={"token": "guest-abc"})
    )
    tok = await guest_token(42, user_info={"username": "alice"})
    assert tok == "guest-abc"


@pytest.mark.anyio
@respx.mock
async def test_ensure_trino_db_creates():
    respx.post(_LOGIN_URL).mock(return_value=httpx.Response(200, json=_LOGIN_PAYLOAD))
    # No existing connection
    respx.get(f"{SUPERSET_URL}/api/v1/database/").mock(
        return_value=httpx.Response(200, json={"count": 0, "result": []})
    )
    respx.post(f"{SUPERSET_URL}/api/v1/database/").mock(
        return_value=httpx.Response(200, json={"id": 7, "database_name": "Codex Trino"})
    )
    result = await ensure_trino_db()
    assert result["status"] == "created"
    assert result["id"] == 7


@pytest.mark.anyio
@respx.mock
async def test_ensure_trino_db_exists():
    respx.post(_LOGIN_URL).mock(return_value=httpx.Response(200, json=_LOGIN_PAYLOAD))
    respx.get(f"{SUPERSET_URL}/api/v1/database/").mock(
        return_value=httpx.Response(200, json={"count": 1, "result": [{"id": 3}]})
    )
    result = await ensure_trino_db()
    assert result["status"] == "exists"


# ─── OpenSearch ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_os_health_green():
    respx.get(f"{OPENSEARCH_URL}/_cluster/health").mock(
        return_value=httpx.Response(200, json={"status": "green"})
    )
    assert await os_health() is True


@pytest.mark.anyio
@respx.mock
async def test_os_health_yellow():
    respx.get(f"{OPENSEARCH_URL}/_cluster/health").mock(
        return_value=httpx.Response(200, json={"status": "yellow"})
    )
    assert await os_health() is True


@pytest.mark.anyio
@respx.mock
async def test_os_health_red():
    respx.get(f"{OPENSEARCH_URL}/_cluster/health").mock(
        return_value=httpx.Response(200, json={"status": "red"})
    )
    assert await os_health() is False


@pytest.mark.anyio
@respx.mock
async def test_os_health_down():
    respx.get(f"{OPENSEARCH_URL}/_cluster/health").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await os_health() is False


@pytest.mark.anyio
@respx.mock
async def test_ensure_index_already_exists():
    respx.head(f"{OPENSEARCH_URL}/{INDEX_NAME}").mock(
        return_value=httpx.Response(200)
    )
    await ensure_index()  # should not call PUT


@pytest.mark.anyio
@respx.mock
async def test_ensure_index_creates():
    respx.head(f"{OPENSEARCH_URL}/{INDEX_NAME}").mock(return_value=httpx.Response(404))
    respx.put(f"{OPENSEARCH_URL}/{INDEX_NAME}").mock(return_value=httpx.Response(200, json={"acknowledged": True}))
    await ensure_index()


@pytest.mark.anyio
@respx.mock
async def test_index_doc():
    respx.put(f"{OPENSEARCH_URL}/{INDEX_NAME}/_doc/test-1").mock(
        return_value=httpx.Response(201, json={"result": "created"})
    )
    await index_doc("test-1", {"name": "foo", "source": "catalog"})


@pytest.mark.anyio
@respx.mock
async def test_bulk_index_empty():
    result = await bulk_index([])
    assert result["indexed"] == 0


@pytest.mark.anyio
@respx.mock
async def test_bulk_index():
    respx.post(f"{OPENSEARCH_URL}/_bulk").mock(
        return_value=httpx.Response(200, json={
            "items": [{"index": {"_id": "a"}}, {"index": {"_id": "b"}}],
            "errors": False,
        })
    )
    result = await bulk_index([
        ("a", {"name": "dataset A"}),
        ("b", {"name": "dataset B"}),
    ])
    assert result["indexed"] == 2
    assert result["errors"] == 0


@pytest.mark.anyio
@respx.mock
async def test_search_returns_hits():
    respx.post(f"{OPENSEARCH_URL}/{INDEX_NAME}/_search").mock(
        return_value=httpx.Response(200, json={
            "hits": {
                "total": {"value": 1},
                "hits": [{"_source": {"name": "sales_data", "source": "catalog"}, "_score": 1.5}],
            },
            "aggregations": {
                "by_source": {"buckets": [{"key": "catalog", "doc_count": 1}]},
                "by_kind":   {"buckets": []},
            },
        })
    )
    result = await search("sales")
    assert result["total"] == 1
    assert result["hits"][0]["name"] == "sales_data"
    assert result["facets"]["by_source"]["catalog"] == 1


@pytest.mark.anyio
@respx.mock
async def test_get_index_stats():
    respx.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_count").mock(
        return_value=httpx.Response(200, json={"count": 42})
    )
    respx.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_stats/store").mock(
        return_value=httpx.Response(200, json={
            "indices": {INDEX_NAME: {"primaries": {"store": {"size_in_bytes": 1024}}}}
        })
    )
    stats = await get_index_stats()
    assert stats["doc_count"] == 42
    assert stats["size_bytes"] == 1024


# ─── Compliance / Falco ───────────────────────────────────────────────────────

def test_parse_falco_line_valid():
    line = json.dumps({
        "time": "2026-05-17T10:00:00Z",
        "rule": "Terminal shell in container",
        "priority": "WARNING",
        "output": "A shell was spawned in a container.",
        "source": "syscall",
        "hostname": "node01",
        "tags": ["container", "shell"],
    })
    ev = _parse_falco_line(line)
    assert ev is not None
    assert ev["rule"] == "Terminal shell in container"
    assert ev["priority"] == "WARNING"


def test_parse_falco_line_invalid():
    assert _parse_falco_line("not json{{{") is None
    assert _parse_falco_line("") is None


def test_read_falco_events_no_file():
    with patch("services.compliance.FALCO_EVENTS_FILE", "/nonexistent/events.json"):
        events = read_falco_events()
    assert events == []


def test_read_falco_events_from_file(tmp_path):
    events_file = tmp_path / "events.json"
    lines = [
        json.dumps({"time": "T1", "rule": "R1", "priority": "CRITICAL", "output": "o1",
                    "source": "syscall", "hostname": "h", "tags": []}),
        json.dumps({"time": "T2", "rule": "R2", "priority": "WARNING",  "output": "o2",
                    "source": "syscall", "hostname": "h", "tags": []}),
    ]
    events_file.write_text("\n".join(lines))
    with patch("services.compliance.FALCO_EVENTS_FILE", str(events_file)):
        events = read_falco_events(limit=10)
    assert len(events) == 2


def test_falco_summary_empty():
    s = falco_summary([])
    assert s["total"] == 0
    assert s["critical"] == 0


def test_falco_summary_counts():
    events = [
        {"priority": "CRITICAL", "rule": "RuleA"},
        {"priority": "CRITICAL", "rule": "RuleA"},
        {"priority": "WARNING",  "rule": "RuleB"},
    ]
    s = falco_summary(events)
    assert s["total"] == 3
    assert s["critical"] == 2
    assert s["by_priority"]["WARNING"] == 1
    assert s["top_rules"][0]["rule"] == "RuleA"
    assert s["top_rules"][0]["count"] == 2


def test_get_scan_summary_no_file():
    with patch("services.compliance.OPENSCAP_RESULTS_DIR", "/nonexistent"):
        summary = get_scan_summary()
    assert summary["available"] is False
    assert summary["score"] is None


def test_get_scan_summary_from_file(tmp_path):
    result = {
        "profile": "cis_l2",
        "scanned_at": "2026-05-17T08:00:00Z",
        "rules": [
            {"id": "r1", "title": "T1", "result": "pass"},
            {"id": "r2", "title": "T2", "result": "pass"},
            {"id": "r3", "title": "T3", "result": "fail"},
        ],
    }
    scan_file = tmp_path / "scan_1.json"
    scan_file.write_text(json.dumps(result))
    with patch("services.compliance.OPENSCAP_RESULTS_DIR", str(tmp_path)):
        summary = get_scan_summary()
    assert summary["available"] is True
    assert summary["pass"] == 2
    assert summary["fail"] == 1
    assert abs(summary["score"] - 66.7) < 0.1
