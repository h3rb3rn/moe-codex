"""Unit tests for services/dossier.py.

Redis is replaced by an in-memory dict that mimics the subset of commands used.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.dossier import (
    create, get, list_all, pin_item, unpin_item, delete,
    DOSSIER_KEY_PREFIX,
)


# ── In-memory Redis stub ──────────────────────────────────────────────────────

class FakeRedis:
    """Minimal Redis stub: set/get/delete/lrange/lpush/ltrim/lrem/expire."""
    def __init__(self):
        self._data: dict = {}
        self._lists: dict = {}

    async def set(self, key, value):
        self._data[key] = value

    async def get(self, key):
        return self._data.get(key)

    async def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]; count += 1
        return count

    async def lpush(self, key, *values):
        if key not in self._lists:
            self._lists[key] = []
        for v in values:
            self._lists[key].insert(0, v)

    async def ltrim(self, key, start, end):
        if key in self._lists:
            self._lists[key] = self._lists[key][start:end + 1]

    async def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        return lst[start: end + 1 if end >= 0 else None]

    async def lrem(self, key, count, value):
        if key in self._lists:
            self._lists[key] = [v for v in self._lists[key] if v != value]

    async def expire(self, key, ttl):
        pass  # not simulated


# ─── create ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_returns_record():
    r = FakeRedis()
    d = await create(r, title="Operation Sunrise", description="Test case")
    assert d["title"] == "Operation Sunrise"
    assert "id" in d
    assert d["items"] == []


@pytest.mark.anyio
async def test_create_no_redis():
    d = await create(None, title="Test")
    assert "error" in d


@pytest.mark.anyio
async def test_create_truncates_long_title():
    r = FakeRedis()
    d = await create(r, title="x" * 300)
    assert len(d["title"]) == 200


# ─── get / list ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_existing():
    r = FakeRedis()
    created = await create(r, title="Alpha")
    fetched = await get(r, created["id"])
    assert fetched is not None
    assert fetched["title"] == "Alpha"


@pytest.mark.anyio
async def test_get_missing():
    r = FakeRedis()
    result = await get(r, "nonexistent")
    assert result is None


@pytest.mark.anyio
async def test_list_all_empty():
    r = FakeRedis()
    items = await list_all(r)
    assert items == []


@pytest.mark.anyio
async def test_list_all_returns_summaries():
    r = FakeRedis()
    await create(r, title="Case A")
    await create(r, title="Case B")
    items = await list_all(r)
    assert len(items) == 2
    titles = {i["title"] for i in items}
    assert "Case A" in titles
    assert "Case B" in titles
    # Summaries should NOT contain items list
    assert "items" not in items[0]


# ─── pin_item ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pin_item():
    r = FakeRedis()
    d = await create(r, title="Investigation")
    item = await pin_item(
        r, d["id"],
        module="graph", kind="entity",
        ref_id="suspect-42", label="Suspect entity from Neo4j",
    )
    assert item is not None
    assert item["module"] == "graph"
    assert item["ref_id"] == "suspect-42"
    assert "item_id" in item


@pytest.mark.anyio
async def test_pin_multiple_items():
    r = FakeRedis()
    d = await create(r, title="Multi-evidence")
    await pin_item(r, d["id"], module="timeline", kind="run", ref_id="run-1", label="First run")
    await pin_item(r, d["id"], module="geo", kind="feature", ref_id="feat-7", label="Location")
    fetched = await get(r, d["id"])
    assert len(fetched["items"]) == 2


@pytest.mark.anyio
async def test_pin_to_missing_dossier():
    r = FakeRedis()
    result = await pin_item(r, "missing-id", module="graph", kind="x", ref_id="y", label="z")
    assert result is None


@pytest.mark.anyio
async def test_pin_note_stored():
    r = FakeRedis()
    d = await create(r, title="With note")
    item = await pin_item(
        r, d["id"],
        module="compliance", kind="alert", ref_id="falco-001",
        label="Shell in container", note="Investigated: false positive",
    )
    assert "false positive" in item["note"]


# ─── unpin_item ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_unpin_item():
    r = FakeRedis()
    d    = await create(r, title="Unpin test")
    item = await pin_item(r, d["id"], module="note", kind="note", ref_id="n1", label="Note 1")
    ok   = await unpin_item(r, d["id"], item["item_id"])
    assert ok is True
    fetched = await get(r, d["id"])
    assert len(fetched["items"]) == 0


@pytest.mark.anyio
async def test_unpin_nonexistent_item():
    r  = FakeRedis()
    d  = await create(r, title="T")
    ok = await unpin_item(r, d["id"], "no-such-item")
    assert ok is False


# ─── delete ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_delete_dossier():
    r  = FakeRedis()
    d  = await create(r, title="To delete")
    ok = await delete(r, d["id"])
    assert ok is True
    assert await get(r, d["id"]) is None


@pytest.mark.anyio
async def test_delete_removes_from_index():
    r = FakeRedis()
    d = await create(r, title="Listed")
    await delete(r, d["id"])
    items = await list_all(r)
    assert not any(i.get("id") == d["id"] for i in items)


@pytest.mark.anyio
async def test_delete_nonexistent():
    r  = FakeRedis()
    ok = await delete(r, "ghost")
    assert ok is False
