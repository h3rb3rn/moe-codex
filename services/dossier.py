"""services/dossier.py — Case file aggregation service (Track D.5).

A dossier is a named investigation container that collects references to
evidence across all Codex modules:
  - Graph entities (from sovereign Neo4j)
  - Timeline events (from Marquez / lakeFS / drift)
  - Documents (from DocLing-parsed files)
  - Notes (from HedgeDoc)
  - Geospatial features (from PostGIS)
  - Compliance events (from Falco)

Dossiers are stored as lightweight JSON records in Redis (key: codex:dossier:<id>).
No new database is required. Each record holds metadata and a list of
pinned item references — the actual data is fetched live from the originating
service when the dossier is opened.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

DOSSIER_KEY_PREFIX = "codex:dossier:"
MAX_DOSSIERS       = 500
DOSSIER_TTL        = int(os.getenv("DOSSIER_TTL_SECONDS", "0"))  # 0 = no expiry


# ─── Redis helpers ────────────────────────────────────────────────────────────

def _key(dossier_id: str) -> str:
    return f"{DOSSIER_KEY_PREFIX}{dossier_id}"


async def create(redis, *, title: str, description: str = "",
                 created_by: str = "") -> dict[str, Any]:
    if redis is None:
        return {"error": "Redis not available — dossiers require Redis"}
    dossier_id = str(uuid.uuid4())[:8]
    record = {
        "id":          dossier_id,
        "title":       title[:200],
        "description": description[:1000],
        "created_by":  created_by,
        "created_at":  int(time.time()),
        "updated_at":  int(time.time()),
        "items":       [],
    }
    await redis.set(_key(dossier_id), json.dumps(record, ensure_ascii=False))
    if DOSSIER_TTL:
        await redis.expire(_key(dossier_id), DOSSIER_TTL)
    # Keep an index list
    await redis.lpush(f"{DOSSIER_KEY_PREFIX}index", dossier_id)
    await redis.ltrim(f"{DOSSIER_KEY_PREFIX}index", 0, MAX_DOSSIERS - 1)
    return record


async def get(redis, dossier_id: str) -> dict[str, Any] | None:
    if redis is None:
        return None
    raw = await redis.get(_key(dossier_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def list_all(redis, limit: int = 50) -> list[dict[str, Any]]:
    if redis is None:
        return []
    ids = await redis.lrange(f"{DOSSIER_KEY_PREFIX}index", 0, limit - 1)
    dossiers = []
    for did in ids:
        d = await get(redis, did)
        if d:
            dossiers.append({k: d[k] for k in ("id", "title", "description",
                                                "created_at", "updated_at")
                             if k in d})
    return dossiers


async def pin_item(redis, dossier_id: str, *,
                   module: str, kind: str, ref_id: str,
                   label: str, note: str = "") -> dict[str, Any] | None:
    """Add a reference to a piece of evidence in the dossier.

    module: 'graph' | 'timeline' | 'document' | 'note' | 'geo' | 'compliance'
    kind:   free-form (e.g. 'entity', 'run', 'feature', 'alert')
    ref_id: the ID/name in the originating system
    label:  human-readable description shown in the dossier
    """
    d = await get(redis, dossier_id)
    if d is None:
        return None
    item = {
        "item_id":  str(uuid.uuid4())[:8],
        "module":   module,
        "kind":     kind,
        "ref_id":   ref_id,
        "label":    label[:300],
        "note":     note[:500],
        "pinned_at": int(time.time()),
    }
    d["items"].append(item)
    d["updated_at"] = int(time.time())
    await redis.set(_key(dossier_id), json.dumps(d, ensure_ascii=False))
    return item


async def unpin_item(redis, dossier_id: str, item_id: str) -> bool:
    d = await get(redis, dossier_id)
    if d is None:
        return False
    before = len(d["items"])
    d["items"] = [i for i in d["items"] if i.get("item_id") != item_id]
    if len(d["items"]) == before:
        return False
    d["updated_at"] = int(time.time())
    await redis.set(_key(dossier_id), json.dumps(d, ensure_ascii=False))
    return True


async def delete(redis, dossier_id: str) -> bool:
    if redis is None:
        return False
    deleted = await redis.delete(_key(dossier_id))
    await redis.lrem(f"{DOSSIER_KEY_PREFIX}index", 0, dossier_id)
    return bool(deleted)
