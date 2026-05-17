"""routes/search.py — Federated Search across all Codex data sources (D.2.6 / D.3.2).

Primary path: OpenSearch full-text index (requires moe-opensearch running).
Fallback path: parallel keyword queries against Marquez, lakeFS, Kestra, lineage
  (used automatically when OpenSearch is unavailable).

Additional endpoints:
  POST /v1/codex/search/index   — trigger re-indexing of catalog into OpenSearch
  GET  /v1/codex/search/stats   — OpenSearch index stats
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services import kestra as kestra_svc
from services import opensearch_client as os_svc

logger = logging.getLogger(__name__)
router = APIRouter()

MARQUEZ_URL   = os.getenv("MARQUEZ_URL",   "")
LAKEFS_URL    = os.getenv("LAKEFS_URL",    "")
LAKEFS_KEY    = os.getenv("LAKEFS_ACCESS_KEY_ID", "")
LAKEFS_SECRET = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "")

_TIMEOUT = 8.0


def _score(text: str, q: str) -> int:
    """Simple relevance score: exact match scores higher than substring match."""
    tl, ql = text.lower(), q.lower()
    if tl == ql:
        return 3
    if tl.startswith(ql):
        return 2
    if ql in tl:
        return 1
    return 0


def _hit(source: str, kind: str, name: str, namespace: str,
         description: str, score: int, extra: dict | None = None) -> dict:
    return {
        "source":      source,
        "kind":        kind,
        "name":        name,
        "namespace":   namespace,
        "description": description,
        "score":       score,
        "extra":       extra or {},
    }


async def _search_catalog(q: str) -> list[dict]:
    if not MARQUEZ_URL:
        return []
    hits: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{MARQUEZ_URL}/api/v1/search", params={"q": q, "limit": 50})
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    name = item.get("name", "")
                    ns   = item.get("namespace", "")
                    sc   = _score(f"{ns}/{name}", q)
                    if sc:
                        hits.append(_hit(
                            "catalog", item.get("type", "dataset"),
                            name, ns, item.get("description", ""), sc,
                        ))
    except Exception as exc:
        logger.debug("search_catalog: %s", exc)
    return hits


async def _search_catalog_namespaces(q: str) -> list[dict]:
    """Fallback: scan all datasets when Marquez /search is not available."""
    if not MARQUEZ_URL:
        return []
    hits: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{MARQUEZ_URL}/api/v1/namespaces")
            if r.status_code != 200:
                return []
            nss = [n["name"] for n in r.json().get("namespaces", [])]
            for ns in nss:
                d = await c.get(f"{MARQUEZ_URL}/api/v1/namespaces/{ns}/datasets",
                                params={"limit": 100})
                if d.status_code != 200:
                    continue
                for ds in d.json().get("datasets", []):
                    name = ds.get("name", "")
                    sc   = _score(f"{ns}/{name}", q)
                    if sc:
                        hits.append(_hit("catalog", "dataset", name, ns, "", sc))
    except Exception as exc:
        logger.debug("search_catalog_namespaces: %s", exc)
    return hits


async def _search_lakefs(q: str) -> list[dict]:
    if not LAKEFS_URL:
        return []
    hits: list[dict] = []
    auth = (LAKEFS_KEY, LAKEFS_SECRET) if LAKEFS_KEY else None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=auth) as c:
            r = await c.get(f"{LAKEFS_URL}/api/v1/repositories", params={"amount": 100})
            if r.status_code != 200:
                return []
            for repo in r.json().get("results", []):
                name = repo.get("id", "")
                sc   = _score(name, q)
                if sc:
                    hits.append(_hit(
                        "versioning", "repository",
                        name, repo.get("storage_namespace", ""),
                        f"branch: {repo.get('default_branch','main')}", sc,
                    ))
    except Exception as exc:
        logger.debug("search_lakefs: %s", exc)
    return hits


async def _search_kestra(q: str) -> list[dict]:
    if not kestra_svc.KESTRA_ENABLED:
        return []
    hits: list[dict] = []
    try:
        data = await kestra_svc.list_flows(size=200)
        for f in data.get("results") or data.get("flows") or []:
            fid = f.get("id", "")
            ns  = f.get("namespace", "")
            sc  = _score(f"{ns}/{fid}", q)
            if sc:
                hits.append(_hit(
                    "pipelines", "flow", fid, ns,
                    f"{len(f.get('tasks') or [])} task(s)", sc,
                ))
    except Exception as exc:
        logger.debug("search_kestra: %s", exc)
    return hits


async def _search_lineage(q: str) -> list[dict]:
    if not MARQUEZ_URL:
        return []
    hits: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{MARQUEZ_URL}/api/v1/jobs", params={"limit": 200})
            if r.status_code != 200:
                return []
            for job in r.json().get("jobs", []):
                name = job.get("name", "")
                ns   = job.get("namespace", "")
                sc   = _score(f"{ns}/{name}", q)
                if sc:
                    hits.append(_hit("lineage", "job", name, ns, "", sc))
    except Exception as exc:
        logger.debug("search_lineage: %s", exc)
    return hits


@router.get("/search")
async def federated_search(q: str = "", limit: int = 50, backend: str = "auto"):
    """Search across catalog, versioning, pipelines, and lineage.

    backend: 'opensearch' | 'fallback' | 'auto' (default — tries OpenSearch first)
    Returns {results: [...], sources: {...counts}, query: str, backend: str}
    """
    if not q or len(q.strip()) < 2:
        return {"results": [], "sources": {}, "query": q,
                "error": "Query must be at least 2 characters."}

    q = q.strip()

    # ── OpenSearch path ─────────────────────────────────────────────────────
    use_opensearch = backend in ("opensearch", "auto")
    if use_opensearch:
        try:
            os_result = await os_svc.search(q, limit=limit)
            if os_result["hits"] or backend == "opensearch":
                hits = os_result["hits"]
                facets = os_result.get("facets", {})
                sources = facets.get("by_source", {})
                return {
                    "query":   q,
                    "results": hits,
                    "total":   os_result["total"],
                    "sources": sources,
                    "facets":  facets,
                    "backend": "opensearch",
                }
        except Exception as exc:
            logger.debug("opensearch backend failed, falling back: %s", exc)

    # ── Fallback: parallel keyword search ──────────────────────────────────
    results = await asyncio.gather(
        _search_catalog(q),
        _search_catalog_namespaces(q),
        _search_lakefs(q),
        _search_kestra(q),
        _search_lineage(q),
        return_exceptions=True,
    )

    all_hits: list[dict] = []
    for group in results:
        if isinstance(group, list):
            all_hits.extend(group)

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for hit in all_hits:
        key = (hit["source"], hit["kind"], hit["name"], hit["namespace"])
        if key not in seen:
            seen.add(key)
            deduped.append(hit)

    deduped.sort(key=lambda h: -h["score"])

    sources: dict[str, int] = {}
    for h in deduped:
        sources[h["source"]] = sources.get(h["source"], 0) + 1

    return {
        "query":   q,
        "results": deduped[:limit],
        "total":   len(deduped),
        "sources": sources,
        "backend": "fallback",
    }


@router.post("/search/index")
async def search_index_catalog():
    """Re-index all catalog datasets into OpenSearch.

    Pulls datasets from Marquez and lakeFS, then bulk-upserts into the
    codex_unified index. Safe to call repeatedly (upsert semantics).
    """
    await os_svc.ensure_index()

    docs: list[tuple[str, dict]] = []

    # Marquez datasets
    if MARQUEZ_URL:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{MARQUEZ_URL}/api/v1/namespaces")
                if r.status_code == 200:
                    for ns_obj in r.json().get("namespaces", []):
                        ns = ns_obj["name"]
                        d = await c.get(
                            f"{MARQUEZ_URL}/api/v1/namespaces/{ns}/datasets",
                            params={"limit": 500},
                        )
                        if d.status_code == 200:
                            for ds in d.json().get("datasets", []):
                                name = ds.get("name", "")
                                doc_id = f"catalog__{ns}__{name}"
                                docs.append((doc_id, {
                                    "id":          doc_id,
                                    "source":      "catalog",
                                    "kind":        ds.get("type", "dataset").lower(),
                                    "name":        name,
                                    "namespace":   ns,
                                    "description": ds.get("description", ""),
                                    "tags":        [t.get("name", "") for t in ds.get("tags", [])],
                                    "updated_at":  ds.get("updatedAt", ""),
                                }))
        except Exception as exc:
            logger.warning("search_index: marquez error: %s", exc)

    # lakeFS repositories
    if LAKEFS_URL:
        try:
            auth = (LAKEFS_KEY, LAKEFS_SECRET) if LAKEFS_KEY else None
            async with httpx.AsyncClient(timeout=10, auth=auth) as c:
                r = await c.get(f"{LAKEFS_URL}/api/v1/repositories", params={"amount": 200})
                if r.status_code == 200:
                    for repo in r.json().get("results", []):
                        name   = repo.get("id", "")
                        doc_id = f"versioning__{name}"
                        docs.append((doc_id, {
                            "id":          doc_id,
                            "source":      "versioning",
                            "kind":        "repository",
                            "name":        name,
                            "namespace":   repo.get("storage_namespace", ""),
                            "description": f"branch:{repo.get('default_branch','main')}",
                            "tags":        [],
                            "updated_at":  "",
                        }))
        except Exception as exc:
            logger.warning("search_index: lakefs error: %s", exc)

    result = await os_svc.bulk_index(docs)
    return {"status": "ok", **result}


@router.get("/search/stats")
async def search_stats():
    """Return OpenSearch index statistics."""
    try:
        stats = await os_svc.get_index_stats()
        healthy = await os_svc.health_check()
        return {"opensearch_reachable": healthy, **stats}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
