"""routes/search.py — Federated Search across all Codex data sources (Phase D.2.6).

Runs parallel async queries against catalog (Marquez + lakeFS), Kestra flows,
lineage job runs, and the knowledge graph. Returns a unified ranked hit list.
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
async def federated_search(q: str = "", limit: int = 50):
    """Search across catalog, versioning, pipelines, and lineage.

    Returns {results: [...], sources: {...counts}, query: str}
    """
    if not q or len(q.strip()) < 2:
        return {"results": [], "sources": {}, "query": q,
                "error": "Query must be at least 2 characters."}

    q = q.strip()

    # Run all searches in parallel
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

    # Deduplicate by (source, kind, name, namespace)
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
    }
