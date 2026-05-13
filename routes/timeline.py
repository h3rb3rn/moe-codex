"""routes/timeline.py — Unified event timeline for vis-timeline (Phase D.2.5).

Aggregates events from three sources into a single chronological list:
- Marquez lineage job runs  (source: "lineage")
- lakeFS versioning commits (source: "versioning")
- Data-health drift events  (source: "health")

The frontend renders these as vis-timeline items grouped by source.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

MARQUEZ_URL      = os.getenv("MARQUEZ_URL", "http://moe-marquez:5000")
LAKEFS_ENDPOINT  = os.getenv("LAKEFS_ENDPOINT", "http://moe-lakefs:8000")
LAKEFS_ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY", "")
LAKEFS_SECRET_KEY = os.getenv("LAKEFS_SECRET_KEY", "")

_WINDOW_DAYS = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}

_GROUPS = [
    {"id": "lineage",    "content": "Lineage runs"},
    {"id": "versioning", "content": "Bundle commits"},
    {"id": "health",     "content": "Drift events"},
]


def _since(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _lineage_items(since: str, limit: int) -> list[dict]:
    items: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{MARQUEZ_URL}/api/v1/jobs/runs",
                params={"limit": limit},
            )
            if r.status_code != 200:
                return items
            for run in r.json().get("runs", []):
                started = run.get("startedAt") or run.get("createdAt") or ""
                if started and started < since:
                    continue
                ended = run.get("endedAt") or ""
                state = run.get("currentState", "")
                cls = {"COMPLETED": "success", "FAILED": "error"}.get(state, "")
                item: dict = {
                    "id":      f"lin-{run.get('id', '')}",
                    "group":   "lineage",
                    "content": run.get("jobName") or run.get("id", "run"),
                    "start":   started,
                    "title":   f"Job: {run.get('jobName','')} · {state}",
                    "className": cls,
                }
                if ended:
                    item["end"] = ended
                items.append(item)
    except Exception as exc:
        logger.debug("lineage timeline error: %s", exc)
    return items


async def _versioning_items(since: str, limit: int) -> list[dict]:
    items: list[dict] = []
    try:
        repo = os.getenv("LAKEFS_REPO", "moe-bundles")
        auth = (LAKEFS_ACCESS_KEY, LAKEFS_SECRET_KEY)
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{LAKEFS_ENDPOINT}/api/v1/repositories/{repo}/commits",
                params={"amount": limit},
                auth=auth,
            )
            if r.status_code != 200:
                return items
            for commit in r.json().get("results", []):
                ts = commit.get("creation_date", 0)
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                else:
                    dt = str(ts)
                if dt < since:
                    continue
                msg = (commit.get("message") or "commit")[:60]
                items.append({
                    "id":      f"ver-{commit.get('id', '')}",
                    "group":   "versioning",
                    "content": msg,
                    "start":   dt,
                    "title":   f"Commit: {msg}\n{commit.get('committer','')}",
                    "className": "success",
                })
    except Exception as exc:
        logger.debug("versioning timeline error: %s", exc)
    return items


async def _health_items(since: str, limit: int) -> list[dict]:
    """Pull drift events from the local Redis event log via the health route."""
    from services.data_health import get_recent_events
    items: list[dict] = []
    try:
        events = await get_recent_events(limit=limit)
        for ev in events:
            ts = ev.get("ts") or ev.get("timestamp") or ""
            if ts and ts < since:
                continue
            severity = ev.get("severity", "info")
            cls = {"critical": "error", "warning": "warning"}.get(severity, "")
            items.append({
                "id":        f"hlt-{ev.get('id', ts)}",
                "group":     "health",
                "content":   ev.get("metric") or ev.get("type") or "drift",
                "start":     ts,
                "title":     ev.get("description") or severity,
                "className": cls,
            })
    except Exception as exc:
        logger.debug("health timeline error: %s", exc)
    return items


@router.get("/timeline")
async def timeline(window: str = "7d", limit: int = 200):
    """Return merged timeline events from lineage, versioning, and drift sources.

    window: time window — '1d', '7d' (default), '30d', '90d'
    limit:  max items per source (capped at 500)
    """
    days  = _WINDOW_DAYS.get(window, 7)
    limit = max(1, min(limit, 500))
    since = _since(days)

    lin, ver, hlt = await _lineage_items(since, limit), [], []
    ver = await _versioning_items(since, limit)
    hlt = await _health_items(since, limit)

    items = lin + ver + hlt
    items.sort(key=lambda x: x.get("start") or "", reverse=True)

    return {
        "window": window,
        "groups": _GROUPS,
        "items":  items[:limit],
        "counts": {
            "lineage":    len(lin),
            "versioning": len(ver),
            "health":     len(hlt),
        },
    }
