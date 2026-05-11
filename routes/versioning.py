"""Knowledge bundle versioning (lakeFS proxy, Phase 18)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.versioning import (
    archive_bundle,
    list_commits,
    _enabled as versioning_enabled,
)

router = APIRouter()


@router.post("/versioning/commit")
async def versioning_commit(raw_request: Request):
    """Archive a knowledge bundle as a lakeFS commit on the default branch.

    For the approval-gated path use /v1/codex/approval/import/pending instead.
    """
    if not versioning_enabled():
        return JSONResponse(status_code=503, content={"error": "lakeFS not configured"})
    try:
        body = await raw_request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    bundle = body.get("bundle", body)
    source_tag = body.get("source_tag", "direct_commit")
    commit_ref = await archive_bundle(bundle, source_tag=source_tag)
    if not commit_ref:
        return JSONResponse(status_code=502, content={"error": "Commit failed"})
    return {"status": "committed", "ref": commit_ref}


@router.get("/versioning/commits")
async def versioning_commits(limit: int = 20):
    """List the most recent commits on the lakeFS default branch."""
    if not versioning_enabled():
        return {"commits": [], "status": "disabled"}
    commits = await list_commits(limit=limit)
    return {"commits": commits, "status": "ok"}
