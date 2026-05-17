"""services/opensearch_client.py — OpenSearch index client (Track D.3.2).

Provides full-text indexing and search across all Codex data sources:
  - Catalog datasets (from Marquez)
  - lakeFS repositories and commits
  - Approval records
  - Knowledge-graph entity summaries

Index schema uses a single codex_unified index with a 'source' field for
post-query faceting. This avoids cross-index coordination overhead and lets
operators run OpenSearch with a single-node dev config.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENSEARCH_URL     = os.getenv("OPENSEARCH_URL", "http://moe-opensearch:9200")
OPENSEARCH_TIMEOUT = float(os.getenv("OPENSEARCH_TIMEOUT", "10"))
INDEX_NAME         = "codex_unified"

_MAPPING = {
    "mappings": {
        "properties": {
            "id":          {"type": "keyword"},
            "source":      {"type": "keyword"},
            "kind":        {"type": "keyword"},
            "name":        {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "namespace":   {"type": "keyword"},
            "description": {"type": "text"},
            "tags":        {"type": "keyword"},
            "updated_at":  {"type": "date", "ignore_malformed": True},
            "extra":       {"type": "object", "enabled": False},
        }
    },
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 0,
    },
}


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OPENSEARCH_URL}/_cluster/health")
            return r.status_code == 200 and r.json().get("status") in ("green", "yellow")
    except Exception:
        return False


async def ensure_index() -> None:
    """Create the unified index with correct mappings if it does not exist."""
    async with httpx.AsyncClient(timeout=OPENSEARCH_TIMEOUT) as c:
        r = await c.head(f"{OPENSEARCH_URL}/{INDEX_NAME}")
        if r.status_code == 200:
            return
        r = await c.put(f"{OPENSEARCH_URL}/{INDEX_NAME}", json=_MAPPING)
        if r.status_code not in (200, 201):
            logger.warning("ensure_index: unexpected %s: %s", r.status_code, r.text[:200])


async def index_doc(doc_id: str, doc: dict[str, Any]) -> None:
    """Upsert a single document into the unified index."""
    async with httpx.AsyncClient(timeout=OPENSEARCH_TIMEOUT) as c:
        r = await c.put(
            f"{OPENSEARCH_URL}/{INDEX_NAME}/_doc/{doc_id}",
            json=doc,
        )
        if r.status_code not in (200, 201):
            logger.debug("index_doc %s: %s", doc_id, r.status_code)


async def bulk_index(docs: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Bulk-upsert documents. docs is a list of (doc_id, doc_body) pairs."""
    if not docs:
        return {"indexed": 0}

    lines: list[str] = []
    for doc_id, body in docs:
        lines.append(f'{{"index":{{"_index":"{INDEX_NAME}","_id":"{doc_id}"}}}}')
        import json
        lines.append(json.dumps(body))
    payload = "\n".join(lines) + "\n"

    async with httpx.AsyncClient(timeout=OPENSEARCH_TIMEOUT) as c:
        r = await c.post(
            f"{OPENSEARCH_URL}/_bulk",
            content=payload,
            headers={"Content-Type": "application/x-ndjson"},
        )
        data = r.json()
        errors = [i for i in data.get("items", []) if "error" in i.get("index", {})]
        if errors:
            logger.warning("bulk_index: %d errors (sample: %s)", len(errors), errors[0])
        return {"indexed": len(docs) - len(errors), "errors": len(errors)}


async def search(
    query: str,
    sources: list[str] | None = None,
    kinds:   list[str] | None = None,
    limit:   int = 50,
) -> dict[str, Any]:
    """Full-text search with optional source/kind filters.

    Returns {hits: [...], total: int, facets: {source: {name: count}}}
    """
    must: list[dict] = [
        {
            "multi_match": {
                "query":  query,
                "fields": ["name^3", "description^2", "namespace", "tags"],
                "type":   "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]
    filters: list[dict] = []
    if sources:
        filters.append({"terms": {"source": sources}})
    if kinds:
        filters.append({"terms": {"kind": kinds}})

    dsl: dict[str, Any] = {
        "query": {
            "bool": {
                "must":   must,
                "filter": filters,
            }
        },
        "size": min(limit, 200),
        "aggs": {
            "by_source": {"terms": {"field": "source", "size": 20}},
            "by_kind":   {"terms": {"field": "kind",   "size": 20}},
        },
        "_source": ["id", "source", "kind", "name", "namespace", "description", "tags", "updated_at"],
    }

    async with httpx.AsyncClient(timeout=OPENSEARCH_TIMEOUT) as c:
        r = await c.post(
            f"{OPENSEARCH_URL}/{INDEX_NAME}/_search",
            json=dsl,
        )
        r.raise_for_status()
        data = r.json()

    hits = [
        {**h["_source"], "score": h["_score"]}
        for h in data.get("hits", {}).get("hits", [])
    ]
    total = data.get("hits", {}).get("total", {})
    total_count = total.get("value", 0) if isinstance(total, dict) else total

    facets: dict[str, dict] = {}
    for agg_key, agg_val in data.get("aggregations", {}).items():
        facets[agg_key] = {
            b["key"]: b["doc_count"]
            for b in agg_val.get("buckets", [])
        }

    return {"hits": hits, "total": total_count, "facets": facets, "query": query}


async def get_index_stats() -> dict[str, Any]:
    """Return document count and index size."""
    async with httpx.AsyncClient(timeout=OPENSEARCH_TIMEOUT) as c:
        r = await c.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_count")
        count = r.json().get("count", 0) if r.status_code == 200 else 0
        s = await c.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_stats/store")
        size_bytes = 0
        if s.status_code == 200:
            size_bytes = (
                s.json()
                .get("indices", {})
                .get(INDEX_NAME, {})
                .get("primaries", {})
                .get("store", {})
                .get("size_in_bytes", 0)
            )
    return {"doc_count": count, "size_bytes": size_bytes}
