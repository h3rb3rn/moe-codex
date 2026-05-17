"""services/hedgedoc.py — HedgeDoc collaborative notes client (Track D.4.3).

HedgeDoc (AGPL) is a real-time collaborative Markdown editor. Moe-codex
integrates it as the Notepad / Reports module, analogous to Palantir's
Foundry Notepad where analysts write documentation with live data embeds.

Integration points:
  1. List notes owned by / shared with the codex admin account.
  2. Create a new note with a given title and initial Markdown content.
  3. Fetch note content (for export or embedding in the admin UI).
  4. Build embed URLs for iframe rendering of published notes.

HedgeDoc's API is session-cookie-based. We maintain a single admin session
whose cookie is refreshed on first use and cached until a 401 forces a retry.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HEDGEDOC_URL      = os.getenv("HEDGEDOC_URL",      "http://moe-hedgedoc:3000")
HEDGEDOC_USER     = os.getenv("HEDGEDOC_USER",     "admin@codex.local")
HEDGEDOC_PASSWORD = os.getenv("HEDGEDOC_PASSWORD", "SovereignNotes!")
HEDGEDOC_TIMEOUT  = float(os.getenv("HEDGEDOC_TIMEOUT", "15"))

_session_cookie: str | None = None


async def _login() -> str | None:
    """Authenticate and return the session cookie value."""
    global _session_cookie
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as c:
            r = await c.post(
                f"{HEDGEDOC_URL}/login",
                data={"email": HEDGEDOC_USER, "password": HEDGEDOC_PASSWORD},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            # HedgeDoc returns 302 on success; session cookie is in Set-Cookie
            cookie = r.headers.get("set-cookie", "")
            if "connect.sid" in cookie or r.status_code in (200, 302):
                _session_cookie = cookie.split(";")[0]
                return _session_cookie
    except Exception as exc:
        logger.debug("hedgedoc login: %s", exc)
    return None


def _cookie_header() -> dict[str, str]:
    if _session_cookie:
        return {"Cookie": _session_cookie}
    return {}


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{HEDGEDOC_URL}/status")
            return r.status_code == 200
    except Exception:
        return False


async def list_notes(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent notes from HedgeDoc."""
    global _session_cookie
    if not _session_cookie:
        await _login()
    try:
        async with httpx.AsyncClient(timeout=HEDGEDOC_TIMEOUT) as c:
            r = await c.get(
                f"{HEDGEDOC_URL}/history",
                headers={**_cookie_header(), "Accept": "application/json"},
            )
            if r.status_code == 401:
                await _login()
                r = await c.get(
                    f"{HEDGEDOC_URL}/history",
                    headers={**_cookie_header(), "Accept": "application/json"},
                )
            if r.status_code == 200:
                data = r.json()
                notes = data.get("history", data) if isinstance(data, dict) else data
                return notes[:limit] if isinstance(notes, list) else []
            return []
    except Exception as exc:
        logger.debug("list_notes: %s", exc)
        return []


async def create_note(title: str, content: str = "") -> dict[str, Any]:
    """Create a new HedgeDoc note and return its {id, url}."""
    global _session_cookie
    if not _session_cookie:
        await _login()
    md = f"# {title}\n\n{content}" if content else f"# {title}\n\n"
    try:
        async with httpx.AsyncClient(timeout=HEDGEDOC_TIMEOUT) as c:
            r = await c.post(
                f"{HEDGEDOC_URL}/new",
                content=md.encode(),
                headers={
                    **_cookie_header(),
                    "Content-Type": "text/markdown",
                },
                follow_redirects=False,
            )
            # HedgeDoc returns 302 to /<note_id>
            if r.status_code in (200, 201, 302):
                note_id = r.headers.get("location", "").lstrip("/")
                return {
                    "id":  note_id,
                    "url": f"{HEDGEDOC_URL}/{note_id}",
                    "title": title,
                }
            return {"error": f"HTTP {r.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


async def get_note(note_id: str) -> str:
    """Fetch the raw Markdown content of a note."""
    try:
        async with httpx.AsyncClient(timeout=HEDGEDOC_TIMEOUT) as c:
            r = await c.get(
                f"{HEDGEDOC_URL}/{note_id}/download",
                headers=_cookie_header(),
            )
            return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def embed_url(note_id: str, read_only: bool = True) -> str:
    """Return the slideshare-style embed URL for a note."""
    suffix = "/view" if read_only else ""
    return f"{HEDGEDOC_URL}/{note_id}{suffix}"
