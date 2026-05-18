"""Unit tests for D4 services: Budibase, TimescaleDB, HedgeDoc, Geospatial.

All HTTP calls are mocked so no external services need to be running.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import respx
import httpx

from services.budibase import (
    health_check as bb_health,
    list_apps,
    app_embed_url,
    BUDIBASE_URL,
)
from services.timeseries import (
    health_check as ts_health,
    list_hypertables,
    query_metric,
    ingest_event,
    TIMESERIES_PGREST_URL,
)
from services.hedgedoc import (
    health_check as hd_health,
    list_notes,
    create_note,
    get_note,
    embed_url,
    HEDGEDOC_URL,
)
from services.geospatial import (
    health_check as geo_health,
    list_layers,
    layer_geojson,
    kepler_config,
    GEO_PGREST_URL,
)


# ─── Budibase ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_budibase_health_ok():
    respx.get(f"{BUDIBASE_URL}/").mock(return_value=httpx.Response(200))
    assert await bb_health() is True


@pytest.mark.anyio
@respx.mock
async def test_budibase_health_down():
    respx.get(f"{BUDIBASE_URL}/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await bb_health() is False


@pytest.mark.anyio
@respx.mock
async def test_list_apps_returns_apps():
    apps = [{"_id": "app1", "name": "Incident Tracker", "status": "published", "public": True}]
    respx.get(f"{BUDIBASE_URL}/api/global/configs/checklist").mock(
        return_value=httpx.Response(200, json={"complete": True})
    )
    respx.get(f"{BUDIBASE_URL}/api/applications").mock(
        return_value=httpx.Response(200, json=apps)
    )
    result = await list_apps()
    assert result["total"] == 1
    assert result["apps"][0]["name"] == "Incident Tracker"


@pytest.mark.anyio
async def test_app_embed_url():
    url = await app_embed_url("app123")
    assert "app123" in url
    assert BUDIBASE_URL in url


# ─── TimescaleDB ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_timeseries_health_ok():
    respx.get(f"{TIMESERIES_PGREST_URL}/").mock(
        return_value=httpx.Response(200)
    )
    assert await ts_health() is True


@pytest.mark.anyio
@respx.mock
async def test_timeseries_health_down():
    respx.get(f"{TIMESERIES_PGREST_URL}/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await ts_health() is False


@pytest.mark.anyio
@respx.mock
async def test_list_hypertables():
    tables = [{"hypertable_name": "sensor_data", "schema_name": "codex"}]
    respx.get(f"{TIMESERIES_PGREST_URL}/timescaledb_information.hypertables").mock(
        return_value=httpx.Response(200, json=tables)
    )
    result = await list_hypertables()
    assert len(result) == 1
    assert result[0]["hypertable_name"] == "sensor_data"


@pytest.mark.anyio
@respx.mock
async def test_query_metric_returns_rows():
    rows = [
        {"time": "2026-05-17T08:00:00Z", "value": 42.5},
        {"time": "2026-05-17T09:00:00Z", "value": 43.1},
    ]
    respx.get(f"{TIMESERIES_PGREST_URL}/codex.sensor_data").mock(
        return_value=httpx.Response(200, json=rows)
    )
    result = await query_metric("sensor_data", window="1d")
    assert result["total"] == 2
    assert result["rows"][0][1] == 42.5


@pytest.mark.anyio
@respx.mock
async def test_ingest_event_ok():
    respx.post(f"{TIMESERIES_PGREST_URL}/codex.events").mock(
        return_value=httpx.Response(201)
    )
    ok = await ingest_event("events", {"time": "2026-05-17T10:00:00Z", "value": 1.0})
    assert ok is True


@pytest.mark.anyio
@respx.mock
async def test_ingest_event_failure():
    respx.post(f"{TIMESERIES_PGREST_URL}/codex.events").mock(
        return_value=httpx.Response(500)
    )
    ok = await ingest_event("events", {"value": 1.0})
    assert ok is False


# ─── HedgeDoc ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_hedgedoc_health_ok():
    respx.get(f"{HEDGEDOC_URL}/status").mock(return_value=httpx.Response(200))
    assert await hd_health() is True


@pytest.mark.anyio
@respx.mock
async def test_hedgedoc_health_down():
    respx.get(f"{HEDGEDOC_URL}/status").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await hd_health() is False


@pytest.mark.anyio
@respx.mock
async def test_list_notes(monkeypatch):
    notes = [{"id": "abc123", "title": "Incident Report", "updatedAt": "2026-05-17"}]
    monkeypatch.setattr("services.hedgedoc._session_cookie", "connect.sid=test")
    respx.get(f"{HEDGEDOC_URL}/history").mock(
        return_value=httpx.Response(200, json={"history": notes})
    )
    result = await list_notes()
    assert len(result) == 1
    assert result[0]["title"] == "Incident Report"


@pytest.mark.anyio
@respx.mock
async def test_create_note():
    import services.hedgedoc as hd_mod
    hd_mod._session_cookie = "connect.sid=test"
    respx.post(f"{HEDGEDOC_URL}/new").mock(
        return_value=httpx.Response(302, headers={"location": "/xyz789"})
    )
    result = await create_note("Test Note", "## Content")
    assert result["id"] == "xyz789"
    assert "xyz789" in result["url"]


@pytest.mark.anyio
@respx.mock
async def test_get_note():
    import services.hedgedoc as hd_mod
    hd_mod._session_cookie = "connect.sid=test"
    respx.get(f"{HEDGEDOC_URL}/abc123/download").mock(
        return_value=httpx.Response(200, text="# My Note\n\nContent here.")
    )
    content = await get_note("abc123")
    assert "My Note" in content


def test_embed_url_readonly():
    url = embed_url("abc123", read_only=True)
    assert "abc123" in url
    assert "/view" in url


def test_embed_url_editable():
    url = embed_url("abc123", read_only=False)
    assert "abc123" in url
    assert "/view" not in url


# ─── Geospatial ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_geo_health_ok():
    respx.get(f"{GEO_PGREST_URL}/").mock(return_value=httpx.Response(200, json={}))
    assert await geo_health() is True


@pytest.mark.anyio
@respx.mock
async def test_geo_health_down():
    respx.get(f"{GEO_PGREST_URL}/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await geo_health() is False


@pytest.mark.anyio
@respx.mock
async def test_list_layers_empty():
    respx.get(f"{GEO_PGREST_URL}/").mock(
        return_value=httpx.Response(200, json={"definitions": []})
    )
    layers = await list_layers()
    assert layers == []


@pytest.mark.anyio
@respx.mock
async def test_layer_geojson():
    rows = [
        {"id": 1, "name": "Berlin", "_geojson": '{"type":"Point","coordinates":[13.4,52.5]}'},
        {"id": 2, "name": "Hamburg", "_geojson": '{"type":"Point","coordinates":[10.0,53.6]}'},
    ]
    respx.get(f"{GEO_PGREST_URL}/codex_geo.districts").mock(
        return_value=httpx.Response(200, json=rows)
    )
    result = await layer_geojson("districts")
    assert result["type"] == "FeatureCollection"
    assert result["count"] == 2
    assert result["features"][0]["geometry"]["type"] == "Point"
    assert result["features"][0]["properties"]["name"] == "Berlin"


@pytest.mark.anyio
@respx.mock
async def test_layer_geojson_empty():
    respx.get(f"{GEO_PGREST_URL}/codex_geo.empty").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = await layer_geojson("empty")
    assert result["count"] == 0
    assert result["features"] == []


def test_kepler_config_structure():
    config = kepler_config("districts", "/api/codex/geo/layers/districts/geojson")
    assert config["version"] == "v1"
    assert config["config"]["visState"]["layers"][0]["type"] == "geojson"
    assert "/api/codex/geo" in config["geojson_url"]
