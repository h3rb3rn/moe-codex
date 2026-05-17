"""Unit tests for core pipeline services: lineage, versioning, etl_pipeline, data_health.

These services were the original Phase 16-18 work and lacked dedicated tests.
All external HTTP calls are mocked with respx; Redis is mocked in-memory.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx


# ═══════════════════════════════════════════════════════════════════════════════
# services/lineage.py
# ═══════════════════════════════════════════════════════════════════════════════

from services.lineage import (
    _now_iso,
    _enabled,
    _dataset,
    _build_event,
    start_run,
    complete_run,
    fail_run,
    dataset_user_query,
    dataset_response,
    dataset_kg,
    dataset_kafka_topic,
    dataset_expert_template,
    NAMESPACE,
    PRODUCER,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def test_now_iso_format():
    ts = _now_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    assert len(ts) >= 20


def test_enabled_false_by_default():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = ""
    assert _enabled() is False
    lin.MARQUEZ_URL = original


def test_enabled_true_when_set():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = "http://marquez:5000"
    assert _enabled() is True
    lin.MARQUEZ_URL = original


def test_dataset_basic():
    d = _dataset("my_dataset")
    assert d["namespace"] == NAMESPACE
    assert d["name"] == "my_dataset"
    assert "facets" not in d


def test_dataset_custom_namespace():
    d = _dataset("my_topic", namespace="kafka")
    assert d["namespace"] == "kafka"


def test_dataset_with_facets():
    d = _dataset("ds", facets={"schema": {"fields": []}})
    assert "facets" in d


def test_build_event_start():
    ev = _build_event(event_type="START", run_id="run-1", job_name="test_job")
    assert ev["eventType"] == "START"
    assert ev["run"]["runId"] == "run-1"
    assert ev["job"]["name"] == "test_job"
    assert ev["job"]["namespace"] == NAMESPACE
    assert ev["producer"] == PRODUCER
    assert ev["inputs"] == []
    assert ev["outputs"] == []


def test_build_event_with_parent():
    ev = _build_event(
        event_type="START", run_id="child-1", job_name="child",
        parent_run_id="parent-1", parent_job_name="parent",
    )
    facets = ev["run"]["facets"]
    assert "parent" in facets
    assert facets["parent"]["run"]["runId"] == "parent-1"


def test_build_event_fail_with_error():
    ev = _build_event(
        event_type="FAIL", run_id="r", job_name="j",
        error="Something went wrong",
    )
    assert "errorMessage" in ev["run"]["facets"]
    assert "Something went wrong" in ev["run"]["facets"]["errorMessage"]["message"]


def test_build_event_error_truncated_at_1000():
    long_error = "x" * 2000
    ev = _build_event(event_type="FAIL", run_id="r", job_name="j", error=long_error)
    assert len(ev["run"]["facets"]["errorMessage"]["message"]) == 1000


# ── start_run / complete_run / fail_run ───────────────────────────────────────

@pytest.mark.anyio
async def test_start_run_returns_run_id():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = ""  # disabled → pure no-op but still returns ID
    run_id = await start_run("test_job")
    assert run_id  # UUID generated even when disabled
    lin.MARQUEZ_URL = original


@pytest.mark.anyio
async def test_start_run_uses_provided_id():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = ""
    run_id = await start_run("j", run_id="my-custom-id")
    assert run_id == "my-custom-id"
    lin.MARQUEZ_URL = original


@pytest.mark.anyio
@respx.mock
async def test_start_run_emits_when_enabled():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = "http://marquez:5000"
    route = respx.post("http://marquez:5000/api/v1/lineage").mock(
        return_value=httpx.Response(201)
    )
    run_id = await start_run("emit_job")
    # Give the background task a chance to fire
    await asyncio.sleep(0.05)
    assert run_id
    lin.MARQUEZ_URL = original


@pytest.mark.anyio
async def test_complete_run_noop_when_disabled():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = ""
    # Should not raise
    await complete_run("r", job_name="j")
    lin.MARQUEZ_URL = original


@pytest.mark.anyio
async def test_fail_run_noop_when_disabled():
    import services.lineage as lin
    original = lin.MARQUEZ_URL
    lin.MARQUEZ_URL = ""
    await fail_run("r", job_name="j", error="oops")
    lin.MARQUEZ_URL = original


# ── dataset builders ──────────────────────────────────────────────────────────

def test_dataset_user_query_no_session():
    d = dataset_user_query()
    assert d["name"] == "user_query"


def test_dataset_user_query_with_session():
    d = dataset_user_query("sess-abc")
    assert "sess-abc" in d["name"]


def test_dataset_response():
    d = dataset_response("chat-123")
    assert "chat-123" in d["name"]


def test_dataset_kg():
    d = dataset_kg()
    assert "kg" in d["name"]
    assert "neo4j" in d["namespace"]


def test_dataset_kafka_topic():
    d = dataset_kafka_topic("moe.events")
    assert d["name"] == "moe.events"
    assert "kafka" in d["namespace"]


def test_dataset_expert_template():
    d = dataset_expert_template("tmpl-42")
    assert "tmpl-42" in d["name"]
    assert "templates" in d["namespace"]


# ═══════════════════════════════════════════════════════════════════════════════
# services/versioning.py
# ═══════════════════════════════════════════════════════════════════════════════

from services.versioning import (
    _enabled as ver_enabled,
    _auth,
    ensure_repository,
    archive_bundle,
    list_commits,
    LAKEFS_ENDPOINT,
    REPO_NAME,
)
import services.versioning as ver_mod


def test_versioning_disabled_by_default():
    original = ver_mod.LAKEFS_ENDPOINT
    ver_mod.LAKEFS_ENDPOINT = ""
    assert ver_enabled() is False
    ver_mod.LAKEFS_ENDPOINT = original


def test_versioning_enabled():
    original = ver_mod.LAKEFS_ENDPOINT
    ver_mod.LAKEFS_ENDPOINT = "http://lakefs:8000"
    assert ver_enabled() is True
    ver_mod.LAKEFS_ENDPOINT = original


def test_auth_returns_none_without_creds(monkeypatch):
    monkeypatch.delenv("LAKEFS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("LAKEFS_SECRET_ACCESS_KEY", raising=False)
    assert _auth() is None


def test_auth_returns_tuple_with_creds(monkeypatch):
    monkeypatch.setenv("LAKEFS_ACCESS_KEY_ID", "mykey")
    monkeypatch.setenv("LAKEFS_SECRET_ACCESS_KEY", "mysecret")
    auth = _auth()
    assert auth == ("mykey", "mysecret")


@pytest.mark.anyio
async def test_ensure_repository_disabled():
    original = ver_mod.LAKEFS_ENDPOINT
    ver_mod.LAKEFS_ENDPOINT = ""
    result = await ensure_repository()
    assert result is False
    ver_mod.LAKEFS_ENDPOINT = original


@pytest.mark.anyio
@respx.mock
async def test_ensure_repository_already_exists(monkeypatch):
    ver_mod.LAKEFS_ENDPOINT = "http://lakefs:8000"
    monkeypatch.setenv("LAKEFS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("LAKEFS_SECRET_ACCESS_KEY", "s")
    ver_mod._repo_ready.clear()

    respx.get(f"http://lakefs:8000/api/v1/repositories/{REPO_NAME}").mock(
        return_value=httpx.Response(200, json={"id": REPO_NAME})
    )
    result = await ensure_repository()
    assert result is True
    ver_mod.LAKEFS_ENDPOINT = ""


@pytest.mark.anyio
@respx.mock
async def test_archive_bundle_disabled():
    original = ver_mod.LAKEFS_ENDPOINT
    ver_mod.LAKEFS_ENDPOINT = ""
    result = await archive_bundle({"entities": []}, source_tag="test")
    assert result is None
    ver_mod.LAKEFS_ENDPOINT = original


@pytest.mark.anyio
@respx.mock
async def test_archive_bundle_success(monkeypatch):
    ver_mod.LAKEFS_ENDPOINT = "http://lakefs:8000"
    monkeypatch.setenv("LAKEFS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("LAKEFS_SECRET_ACCESS_KEY", "s")
    ver_mod._repo_ready.add(REPO_NAME)  # skip ensure_repository

    respx.post(f"http://lakefs:8000/api/v1/repositories/{REPO_NAME}/branches/main/objects").mock(
        return_value=httpx.Response(201)
    )
    respx.post(f"http://lakefs:8000/api/v1/repositories/{REPO_NAME}/branches/main/commits").mock(
        return_value=httpx.Response(201, json={"id": "abc123def"})
    )
    result = await archive_bundle({"entities": [{"id": "e1"}]}, source_tag="unit_test")
    assert result == "abc123def"
    ver_mod.LAKEFS_ENDPOINT = ""
    ver_mod._repo_ready.clear()


@pytest.mark.anyio
async def test_list_commits_disabled():
    original = ver_mod.LAKEFS_ENDPOINT
    ver_mod.LAKEFS_ENDPOINT = ""
    result = await list_commits()
    assert result == []
    ver_mod.LAKEFS_ENDPOINT = original


# ═══════════════════════════════════════════════════════════════════════════════
# services/etl_pipeline.py
# ═══════════════════════════════════════════════════════════════════════════════

from services.etl_pipeline import (
    _submit_enabled,
    submit_to_pipeline,
    get_system_diagnostics,
    summarise_diagnostics,
    NIFI_INGEST_URL,
)
import services.etl_pipeline as etl_mod


def test_submit_disabled_by_default():
    original = etl_mod.NIFI_INGEST_URL
    etl_mod.NIFI_INGEST_URL = ""
    assert _submit_enabled() is False
    etl_mod.NIFI_INGEST_URL = original


def test_submit_enabled():
    original = etl_mod.NIFI_INGEST_URL
    etl_mod.NIFI_INGEST_URL = "http://nifi:8081/moe"
    assert _submit_enabled() is True
    etl_mod.NIFI_INGEST_URL = original


@pytest.mark.anyio
async def test_submit_noop_when_disabled():
    original = etl_mod.NIFI_INGEST_URL
    etl_mod.NIFI_INGEST_URL = ""
    result = await submit_to_pipeline({"key": "val"}, source="test")
    assert result is False
    etl_mod.NIFI_INGEST_URL = original


@pytest.mark.anyio
@respx.mock
async def test_submit_success():
    etl_mod.NIFI_INGEST_URL = "http://nifi:8081/moe"
    respx.post("http://nifi:8081/moe").mock(return_value=httpx.Response(200))
    result = await submit_to_pipeline({"entity": "e1"}, source="unit_test",
                                      metadata={"domain": "test"})
    assert result is True
    etl_mod.NIFI_INGEST_URL = ""


@pytest.mark.anyio
@respx.mock
async def test_submit_failure_on_non_2xx():
    etl_mod.NIFI_INGEST_URL = "http://nifi:8081/moe"
    respx.post("http://nifi:8081/moe").mock(return_value=httpx.Response(500))
    result = await submit_to_pipeline({"entity": "e1"}, source="test")
    assert result is False
    etl_mod.NIFI_INGEST_URL = ""


@pytest.mark.anyio
@respx.mock
async def test_submit_failure_on_network_error():
    etl_mod.NIFI_INGEST_URL = "http://nifi:8081/moe"
    respx.post("http://nifi:8081/moe").mock(side_effect=httpx.ConnectError("refused"))
    result = await submit_to_pipeline({"entity": "e1"}, source="test")
    assert result is False
    etl_mod.NIFI_INGEST_URL = ""


@pytest.mark.anyio
async def test_get_diagnostics_disabled():
    original = etl_mod.NIFI_URL
    etl_mod.NIFI_URL = ""
    result = await get_system_diagnostics()
    assert result is None
    etl_mod.NIFI_URL = original


def test_summarise_diagnostics_none():
    result = summarise_diagnostics(None)
    assert result == {"available": False}


def test_summarise_diagnostics_full():
    diag = {
        "systemDiagnostics": {
            "aggregateSnapshot": {
                "uptime":                "2 days",
                "freeHeap":              "512 MB",
                "maxHeap":               "1 GB",
                "heapUtilization":       "50%",
                "availableProcessors":   4,
                "totalThreads":          32,
                "versionInfo":           {"niFiVersion": "1.27.0"},
            }
        }
    }
    result = summarise_diagnostics(diag)
    assert result["available"] is True
    assert result["uptime"] == "2 days"
    assert result["version"] == "1.27.0"
    assert result["available_processors"] == 4


def test_summarise_diagnostics_empty_snapshot():
    result = summarise_diagnostics({"systemDiagnostics": {}})
    assert result["available"] is True
    assert result["uptime"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# services/data_health.py
# ═══════════════════════════════════════════════════════════════════════════════

from services.sovereign_client import (
    health_check as sov_health,
    graph_stats,
    graph_domains,
    knowledge_import,
    cypher_read,
    SOVEREIGN_URL,
)
import services.sovereign_client as sov_mod


# ═══════════════════════════════════════════════════════════════════════════════
# services/sovereign_client.py
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
@respx.mock
async def test_sov_health_ok():
    respx.get(f"{SOVEREIGN_URL}/health").mock(return_value=httpx.Response(200))
    assert await sov_health() is True


@pytest.mark.anyio
@respx.mock
async def test_sov_health_down():
    respx.get(f"{SOVEREIGN_URL}/health").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await sov_health() is False


@pytest.mark.anyio
@respx.mock
async def test_sov_health_non_200():
    respx.get(f"{SOVEREIGN_URL}/health").mock(return_value=httpx.Response(503))
    assert await sov_health() is False


@pytest.mark.anyio
@respx.mock
async def test_graph_stats():
    respx.get(f"{SOVEREIGN_URL}/graph/stats").mock(
        return_value=httpx.Response(200, json={"entities": 42, "relations": 100})
    )
    result = await graph_stats()
    assert result["entities"] == 42


@pytest.mark.anyio
@respx.mock
async def test_graph_domains():
    respx.get(f"{SOVEREIGN_URL}/graph/domains").mock(
        return_value=httpx.Response(200, json={"domains": ["legal", "medical"]})
    )
    result = await graph_domains()
    assert "domains" in result


@pytest.mark.anyio
@respx.mock
async def test_knowledge_import():
    respx.post(f"{SOVEREIGN_URL}/graph/knowledge/import").mock(
        return_value=httpx.Response(200, json={"imported": 5, "skipped": 0})
    )
    result = await knowledge_import(
        bundle={"entities": [{"id": "e1"}]},
        source_tag="test_import",
        trust_floor=0.7,
    )
    assert result["imported"] == 5


@pytest.mark.anyio
@respx.mock
async def test_knowledge_import_sends_trust_floor():
    route = respx.post(f"{SOVEREIGN_URL}/graph/knowledge/import").mock(
        return_value=httpx.Response(200, json={})
    )
    await knowledge_import({"entities": []}, source_tag="t", trust_floor=0.5)
    body = route.calls[0].request.content
    assert b"trust_floor" in body
    assert b"0.5" in body


@pytest.mark.anyio
@respx.mock
async def test_cypher_read():
    respx.post(f"{SOVEREIGN_URL}/graph/cypher/read").mock(
        return_value=httpx.Response(200, json={"rows": [{"name": "Berlin"}]})
    )
    result = await cypher_read("MATCH (n) RETURN n.name AS name LIMIT 1")
    assert result["rows"][0]["name"] == "Berlin"


@pytest.mark.anyio
@respx.mock
async def test_cypher_read_with_api_key():
    sov_mod.SOVEREIGN_API_KEY = "test-key-123"
    route = respx.post(f"{SOVEREIGN_URL}/graph/cypher/read").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    await cypher_read("MATCH (n) RETURN n LIMIT 1")
    auth = route.calls[0].request.headers.get("authorization", "")
    assert "test-key-123" in auth
    sov_mod.SOVEREIGN_API_KEY = ""


from services.data_health import (
    compute_drift,
    record_event,
    recent_events,
    EVENT_KEY,
)


# ── compute_drift: pure function, many scenarios ──────────────────────────────

def test_drift_ok_small_import():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 105, "relations": 210}
    result = compute_drift(before, after, declared_entities=5)
    assert result["severity"] == "info"
    assert result["delta_entities"] == 5
    assert result["flags"] == []


def test_drift_crit_zero_entities_added():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 100, "relations": 200}
    result = compute_drift(before, after, declared_entities=10)
    assert result["severity"] == "crit"
    assert "zero_entities_added" in result["flags"]


def test_drift_crit_entity_count_shrank():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 95, "relations": 200}
    result = compute_drift(before, after, declared_entities=10)
    assert result["severity"] == "crit"
    assert "entity_count_shrank" in result["flags"]


def test_drift_warn_entity_dedup_suppressed():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 101, "relations": 200}
    # Declared 50, only 1 added → heavy dedup
    result = compute_drift(before, after, declared_entities=50)
    assert result["severity"] == "warn"
    assert "entity_dedup_suppressed" in result["flags"]


def test_drift_warn_entity_overshoot():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 150, "relations": 200}
    # Declared 10, got 50 → overshoot
    result = compute_drift(before, after, declared_entities=10)
    assert result["severity"] == "warn"
    assert "entity_overshoot" in result["flags"]


def test_drift_warn_relation_to_entity_explosion():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 110, "relations": 260}
    # 10 new entities, 60 new relations → 6x ratio (threshold is 5x)
    result = compute_drift(before, after, declared_entities=10)
    assert "relation_to_entity_explosion" in result["flags"]


def test_drift_ok_for_empty_declared():
    """When declared_entities == 0 entity checks are skipped."""
    before = {"entities": 100}
    after  = {"entities": 100}
    result = compute_drift(before, after, declared_entities=0)
    assert result["severity"] == "ok"


def test_drift_relation_overshoot():
    before = {"entities": 100, "relations": 200}
    after  = {"entities": 105, "relations": 280}
    result = compute_drift(before, after, declared_entities=5, declared_relations=10)
    assert "relation_overshoot" in result["flags"]


def test_drift_delta_fields():
    before = {"entities": 100, "relations": 200, "synthesis_nodes": 10}
    after  = {"entities": 103, "relations": 206, "synthesis_nodes": 12}
    result = compute_drift(before, after, declared_entities=3)
    assert result["delta_entities"] == 3
    assert result["delta_relations"] == 6
    assert result["delta_synthesis"] == 2


# ── record_event / recent_events: Redis mocked ───────────────────────────────

@pytest.mark.anyio
async def test_record_event_noop_without_redis():
    await record_event(None, source_tag="test", drift={"severity": "ok", "flags": []})
    # no exception


@pytest.mark.anyio
async def test_record_event_calls_redis():
    """Mock Redis pipeline to verify correct calls."""
    pipe   = MagicMock()
    pipe.lpush = MagicMock()
    pipe.ltrim  = MagicMock()
    pipe.execute = AsyncMock(return_value=None)

    redis  = AsyncMock()
    redis.pipeline = MagicMock(return_value=pipe)

    drift = {"severity": "warn", "flags": ["entity_dedup_suppressed"], "delta_entities": 1}
    await record_event(redis, source_tag="test_import", drift=drift, trust_floor=0.6)

    pipe.lpush.assert_called_once()
    key, payload = pipe.lpush.call_args[0]
    assert key == EVENT_KEY
    data = json.loads(payload)
    assert data["source_tag"] == "test_import"
    assert data["severity"] == "warn"
    assert data["trust_floor"] == 0.6


@pytest.mark.anyio
async def test_recent_events_noop_without_redis():
    result = await recent_events(None)
    assert result == []


@pytest.mark.anyio
async def test_recent_events_returns_parsed_events():
    ev1 = {"ts": 1000, "severity": "ok", "flags": []}
    ev2 = {"ts": 2000, "severity": "warn", "flags": ["dedup"]}
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[
        json.dumps(ev2).encode(),
        json.dumps(ev1).encode(),
    ])
    result = await recent_events(redis, limit=10)
    assert len(result) == 2
    assert result[0]["severity"] == "warn"


@pytest.mark.anyio
async def test_recent_events_skips_malformed():
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[b"not-json", b'{"ts": 1}'])
    result = await recent_events(redis, limit=10)
    assert len(result) == 1
    assert result[0]["ts"] == 1
