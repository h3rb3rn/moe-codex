"""Unit tests for services/opa.py.

These tests mock the HTTP calls so OPA does not need to be running.
"""
from __future__ import annotations

import pytest
import respx
import httpx

from services.opa import (
    evaluate,
    catalog_allow,
    approval_allow,
    marking_allow,
    _extract_user,
    OPA_URL,
)


# ─── _extract_user ────────────────────────────────────────────────────────────

def test_extract_user_defaults():
    user = _extract_user({})
    assert user["id"] == ""
    assert user["groups"] == []
    assert user["clearance"] == "PUBLIC"


def test_extract_user_full():
    headers = {
        "x-codex-user-id": "alice",
        "x-codex-groups":  "admin,approver",
        "x-codex-clearance": "CONFIDENTIAL",
    }
    user = _extract_user(headers)
    assert user["id"] == "alice"
    assert "admin" in user["groups"]
    assert "approver" in user["groups"]
    assert user["clearance"] == "CONFIDENTIAL"


# ─── evaluate ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_evaluate_allow_true():
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": True}))
    result = await evaluate("codex.catalog", "allow", {"user": {}, "dataset": {}, "action": "read"})
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_evaluate_allow_false():
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": False}))
    result = await evaluate("codex.catalog", "allow", {"user": {}, "dataset": {}, "action": "read"})
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_evaluate_opa_down_fail_closed(monkeypatch):
    monkeypatch.setattr("services.opa.OPA_FAIL_OPEN", False)
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(side_effect=httpx.ConnectError("down"))
    result = await evaluate("codex.catalog", "allow", {})
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_evaluate_opa_down_fail_open(monkeypatch):
    monkeypatch.setattr("services.opa.OPA_FAIL_OPEN", True)
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(side_effect=httpx.ConnectError("down"))
    result = await evaluate("codex.catalog", "allow", {})
    assert result is True


# ─── catalog_allow ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_catalog_allow_public_dataset():
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": True}))
    user    = {"id": "bob", "groups": [], "clearance": "PUBLIC"}
    dataset = {"name": "public-ds", "classification": "PUBLIC", "owner_group": ""}
    assert await catalog_allow(user, dataset, "read") is True


@pytest.mark.asyncio
@respx.mock
async def test_catalog_allow_restricted_denied():
    url = f"{OPA_URL}/v1/data/codex/catalog/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": False}))
    user    = {"id": "bob", "groups": [], "clearance": "PUBLIC"}
    dataset = {"name": "secret-ds", "classification": "RESTRICTED", "owner_group": ""}
    assert await catalog_allow(user, dataset, "read") is False


# ─── approval_allow ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_approval_allow_approver():
    url = f"{OPA_URL}/v1/data/codex/approval/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": True}))
    user = {"id": "alice", "groups": ["approver"], "clearance": "INTERNAL"}
    assert await approval_allow(user, "approve") is True


@pytest.mark.asyncio
@respx.mock
async def test_approval_allow_non_approver_denied():
    url = f"{OPA_URL}/v1/data/codex/approval/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": False}))
    user = {"id": "charlie", "groups": ["viewer"], "clearance": "INTERNAL"}
    assert await approval_allow(user, "approve") is False


# ─── marking_allow ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_marking_allow_sufficient_clearance():
    url = f"{OPA_URL}/v1/data/codex/data_markings/allow"
    respx.post(url).mock(return_value=httpx.Response(200, json={"result": True}))
    user    = {"id": "alice", "groups": [], "clearance": "CONFIDENTIAL"}
    dataset = {"classification": "RESTRICTED"}
    assert await marking_allow(user, dataset) is True
