"""Data Catalog cross-source aggregator (Phase 20).

Pulls dataset records from Marquez (lineage), moe-sovereign /graph/domains
(Neo4j), and lakeFS (versioned bundles) into a single searchable list.

Marquez and lakeFS calls are inline HTTP — the service modules expose the
write paths but not the catalog read paths.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request

from services.sovereign_client import graph_domains
from services.lineage import _enabled as lineage_enabled
from services.versioning import _enabled as versioning_enabled

router = APIRouter()

MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://moe-marquez:5000")
LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT", "http://moe-lakefs:8000")
LAKEFS_ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY", "")
LAKEFS_SECRET_KEY = os.getenv("LAKEFS_SECRET_KEY", "")


async def _marquez_datasets() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{MARQUEZ_URL}/api/v1/namespaces")
        r.raise_for_status()
        namespaces = [n["name"] for n in r.json().get("namespaces", [])]
        out: list[dict] = []
        for ns in namespaces:
            d = await c.get(f"{MARQUEZ_URL}/api/v1/namespaces/{ns}/datasets")
            if d.status_code == 200:
                for ds in d.json().get("datasets", []):
                    out.append({
                        "namespace": ns,
                        "name":      ds.get("name", "<unnamed>"),
                        "fields":    ds.get("fields", []),
                    })
        return out


async def _lakefs_repositories() -> list[dict]:
    auth = (LAKEFS_ACCESS_KEY, LAKEFS_SECRET_KEY) if LAKEFS_ACCESS_KEY else None
    async with httpx.AsyncClient(timeout=10, auth=auth) as c:
        r = await c.get(f"{LAKEFS_ENDPOINT}/api/v1/repositories")
        r.raise_for_status()
        repos = r.json().get("results", [])
        out: list[dict] = []
        for repo in repos:
            rid = repo.get("id")
            branches: list[str] = []
            commits = 0
            try:
                b = await c.get(f"{LAKEFS_ENDPOINT}/api/v1/repositories/{rid}/branches")
                if b.status_code == 200:
                    branches = [x.get("id") for x in b.json().get("results", [])]
                cmt = await c.get(f"{LAKEFS_ENDPOINT}/api/v1/repositories/{rid}/refs/main/commits")
                if cmt.status_code == 200:
                    commits = len(cmt.json().get("results", []))
            except Exception:
                pass
            out.append({
                "id":             rid,
                "namespace":      repo.get("storage_namespace", "knowledge").rsplit("/", 1)[-1],
                "default_branch": repo.get("default_branch", "main"),
                "branch_count":   len(branches),
                "commit_count":   commits,
            })
        return out


@router.get("/catalog/datasets")
async def catalog_datasets(request: Request):
    """Aggregate Marquez datasets + Neo4j domains + lakeFS repos.

    OPA filters the result list: only datasets the requesting user may read
    are returned. When OPA is not configured (OPA_ENABLED=false) all items
    are returned (backward compatible with un-enforced deployments).
    """
    items: list[dict] = []
    totals: dict[str, int] = {"marquez": 0, "neo4j": 0, "lakefs": 0}

    # Marquez
    if lineage_enabled():
        try:
            for ds in await _marquez_datasets():
                items.append({
                    "source":    "marquez",
                    "namespace": ds["namespace"],
                    "name":      ds["name"],
                    "type":      "dataset",
                    "size":      None,
                    "metadata":  {"fields": len(ds.get("fields", []))},
                })
            totals["marquez"] = sum(1 for i in items if i["source"] == "marquez")
        except Exception:
            pass

    # Neo4j domains via sovereign
    try:
        sov = await graph_domains()
        for d in sov.get("domains", []):
            items.append({
                "source":    "neo4j",
                "namespace": "knowledge_graph",
                "name":      d["domain"],
                "type":      "domain",
                "size":      d.get("entities", 0),
                "metadata":  {
                    "relations":       d.get("relations", 0),
                    "synthesis_nodes": d.get("synthesis_nodes", 0),
                },
            })
        totals["neo4j"] = sum(1 for i in items if i["source"] == "neo4j")
    except Exception:
        pass

    # lakeFS
    if versioning_enabled():
        try:
            for r in await _lakefs_repositories():
                items.append({
                    "source":    "lakefs",
                    "namespace": r["namespace"],
                    "name":      r["id"],
                    "type":      "repository",
                    "size":      r["commit_count"],
                    "metadata":  {
                        "branches":       r["branch_count"],
                        "default_branch": r["default_branch"],
                    },
                })
            totals["lakefs"] = sum(1 for i in items if i["source"] == "lakefs")
        except Exception:
            pass

    # OPA filtering — items without a classification default to PUBLIC (always visible)
    from services.opa import catalog_allow, _extract_user, OPA_ENABLED
    if OPA_ENABLED:
        user = _extract_user(dict(request.headers))
        filtered: list[dict] = []
        for item in items:
            ds = {
                "name":            item.get("name", ""),
                "namespace":       item.get("namespace", ""),
                "classification":  item.get("classification", "PUBLIC"),
                "owner_group":     item.get("owner_group", ""),
            }
            if await catalog_allow(user, ds, "read"):
                filtered.append(item)
        items = filtered

    totals = {
        "marquez": sum(1 for i in items if i["source"] == "marquez"),
        "neo4j":   sum(1 for i in items if i["source"] == "neo4j"),
        "lakefs":  sum(1 for i in items if i["source"] == "lakefs"),
    }
    return {"items": items, "totals": totals}
