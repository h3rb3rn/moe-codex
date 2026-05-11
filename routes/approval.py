"""Branch-based approval workflow (Phase 21).

Stages incoming knowledge bundles on lakeFS `pending/<tag>-<ts>` branches.
On approval, calls moe-sovereign to import the bundle into Neo4j and then
merges the lakeFS branch into main.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import state
from services.sovereign_client import knowledge_import
from services.data_health import compute_drift, record_event

router = APIRouter()


@router.post("/approval/import/pending")
async def approval_import_pending(raw_request: Request):
    """Stage a bundle on a lakeFS pending branch — no Neo4j write yet."""
    try:
        body = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    bundle = body.get("bundle", body)
    source_tag = body.get("source_tag", "community_import")
    if "@context" not in bundle and "entities" not in bundle:
        return JSONResponse(status_code=400, content={"error": "Not a valid knowledge bundle"})

    from services.versioning import archive_to_branch, _enabled as versioning_enabled
    if not versioning_enabled():
        return JSONResponse(
            status_code=503,
            content={"error": "lakeFS not configured — set LAKEFS_ENDPOINT"},
        )

    branch = await archive_to_branch(
        bundle,
        source_tag=source_tag,
        metadata={
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "entity_count": str(len(bundle.get("entities", []))),
        },
    )
    if not branch:
        return JSONResponse(status_code=502, content={"error": "Failed to stage on lakeFS"})
    return {"status": "pending", "branch": branch, "source_tag": source_tag}


@router.get("/approval/list")
async def approval_list():
    """List all pending knowledge-bundle branches awaiting admin approval."""
    from services.versioning import list_pending_branches, _enabled as versioning_enabled
    if not versioning_enabled():
        return {"status": "disabled", "pending": []}
    pending = await list_pending_branches()
    return {"status": "ok", "pending": pending}


@router.post("/approval/{branch:path}/approve")
async def approval_approve(branch: str, raw_request: Request):
    """Approve a pending branch.

    Flow:
        1. Read bundle from branch head metadata
        2. Snapshot graph stats via moe-sovereign
        3. POST bundle to moe-sovereign /v1/graph/knowledge/import
        4. Re-snapshot graph stats
        5. Compute drift, record event to local Redis
        6. Merge lakeFS branch into main
    """
    from services.versioning import (
        get_bundle_from_branch, approve_branch as approve_lakefs_branch,
        _enabled as versioning_enabled,
    )
    if not versioning_enabled():
        return JSONResponse(status_code=503, content={"error": "lakeFS not configured"})

    bundle = await get_bundle_from_branch(branch)
    if not bundle:
        return JSONResponse(status_code=404, content={"error": f"No bundle found on {branch}"})

    try:
        body = await raw_request.json()
    except Exception:
        body = {}
    approver: str = body.get("approver", "admin")
    trust_floor: float = float(body.get("trust_floor", 0.5))
    source_tag: str = body.get("source_tag") or branch.split("/", 1)[-1].rsplit("-", 1)[0]

    # 1+2. Snapshot before
    from services.sovereign_client import graph_stats
    try:
        before_stats = await graph_stats()
    except Exception:
        before_stats = {}

    # 3. Forward to sovereign
    try:
        sovereign_resp = await knowledge_import(
            bundle=bundle, source_tag=source_tag, trust_floor=trust_floor,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": f"sovereign import failed: {exc}"},
        )

    # 4+5. Drift snapshot
    try:
        after_stats = await graph_stats()
        drift = compute_drift(
            before_stats, after_stats,
            declared_entities=len(bundle.get("entities", [])),
            declared_relations=len(bundle.get("relations", [])) or None,
        )
        if state.redis_client is not None:
            await record_event(state.redis_client, source_tag=source_tag,
                               drift=drift, trust_floor=trust_floor)
    except Exception:
        drift = None

    # 6. lakeFS merge
    merge_ref = await approve_lakefs_branch(branch, approver=approver)
    return {
        "status":   "approved",
        "branch":   branch,
        "merge":    merge_ref,
        "approver": approver,
        "imported": sovereign_resp,
        "drift":    drift,
    }


@router.post("/approval/{branch:path}/reject")
async def approval_reject(branch: str, raw_request: Request):
    """Reject a pending branch: delete it without importing."""
    from services.versioning import reject_branch, _enabled as versioning_enabled
    if not versioning_enabled():
        return JSONResponse(status_code=503, content={"error": "lakeFS not configured"})
    try:
        body = await raw_request.json()
    except Exception:
        body = {}
    rejector: str = body.get("rejector", "admin")
    ok: bool = await reject_branch(branch)
    if not ok:
        return JSONResponse(status_code=502, content={"error": "Failed to reject branch"})
    return {"status": "rejected", "branch": branch, "rejector": rejector}
