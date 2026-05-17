"""Unit tests for services/kestra.py.

HTTP calls are intercepted with respx so Kestra does not need to be running.
"""
from __future__ import annotations

import pytest
import respx
import httpx

from services.kestra import (
    health_check,
    list_flows,
    get_flow,
    trigger_flow,
    list_executions,
    get_execution,
    KESTRA_URL,
)


# ─── service layer ────────────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_health_check_ok():
    respx.get(f"{KESTRA_URL}/api/v1/flows/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    assert await health_check() is True


@pytest.mark.anyio
@respx.mock
async def test_health_check_failure():
    respx.get(f"{KESTRA_URL}/api/v1/flows/search").mock(
        return_value=httpx.Response(500)
    )
    assert await health_check() is False


@pytest.mark.anyio
@respx.mock
async def test_health_check_network_error():
    respx.get(f"{KESTRA_URL}/api/v1/flows/search").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await health_check() is False


@pytest.mark.anyio
@respx.mock
async def test_list_flows_no_namespace():
    payload = {"results": [{"id": "f1", "namespace": "prod"}], "total": 1}
    respx.get(f"{KESTRA_URL}/api/v1/flows/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await list_flows()
    assert result["total"] == 1
    assert result["results"][0]["id"] == "f1"


@pytest.mark.anyio
@respx.mock
async def test_list_flows_with_namespace():
    route = respx.get(f"{KESTRA_URL}/api/v1/flows/search").mock(
        return_value=httpx.Response(200, json={"results": [], "total": 0})
    )
    await list_flows(namespace="prod", page=2, size=10)
    assert route.called
    sent = route.calls[0].request
    assert b"namespace=prod" in sent.url.query
    assert b"page=2" in sent.url.query


@pytest.mark.anyio
@respx.mock
async def test_get_flow():
    payload = {"id": "my-flow", "namespace": "prod", "tasks": []}
    respx.get(f"{KESTRA_URL}/api/v1/flows/prod/my-flow").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await get_flow("prod", "my-flow")
    assert result["id"] == "my-flow"


@pytest.mark.anyio
@respx.mock
async def test_get_flow_not_found_raises():
    respx.get(f"{KESTRA_URL}/api/v1/flows/x/y").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await get_flow("x", "y")


@pytest.mark.anyio
@respx.mock
async def test_trigger_flow_no_inputs():
    exec_payload = {"id": "exec-123", "state": {"current": "CREATED"}}
    respx.post(f"{KESTRA_URL}/api/v1/executions/prod/etl").mock(
        return_value=httpx.Response(200, json=exec_payload)
    )
    result = await trigger_flow("prod", "etl")
    assert result["id"] == "exec-123"


@pytest.mark.anyio
@respx.mock
async def test_trigger_flow_with_inputs():
    exec_payload = {"id": "exec-456", "state": {"current": "CREATED"}}
    route = respx.post(f"{KESTRA_URL}/api/v1/executions/prod/etl").mock(
        return_value=httpx.Response(200, json=exec_payload)
    )
    await trigger_flow("prod", "etl", inputs={"source": "s3://bucket/data.csv"})
    body = route.calls[0].request.content
    assert b"source" in body


@pytest.mark.anyio
@respx.mock
async def test_list_executions():
    payload = {"results": [{"id": "e1"}, {"id": "e2"}], "total": 2}
    respx.get(f"{KESTRA_URL}/api/v1/executions/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await list_executions()
    assert len(result["results"]) == 2


@pytest.mark.anyio
@respx.mock
async def test_list_executions_filtered():
    route = respx.get(f"{KESTRA_URL}/api/v1/executions/search").mock(
        return_value=httpx.Response(200, json={"results": [], "total": 0})
    )
    await list_executions(namespace="prod", flow_id="etl", page=1, size=25)
    sent = route.calls[0].request
    assert b"flowId=etl" in sent.url.query


@pytest.mark.anyio
@respx.mock
async def test_get_execution():
    payload = {"id": "exec-789", "state": {"current": "SUCCESS"}}
    respx.get(f"{KESTRA_URL}/api/v1/executions/exec-789").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await get_execution("exec-789")
    assert result["state"]["current"] == "SUCCESS"

