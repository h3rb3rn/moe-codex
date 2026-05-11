"""services/opa.py — Open Policy Agent client.

Evaluates access-control decisions by posting input documents to OPA's
REST API (POST /v1/data/<package>/<rule>).

If OPA is unreachable and OPA_FAIL_OPEN=true (default: false), all
decisions fall back to allow=True so the system degrades gracefully
during a cold-start rather than locking everyone out.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPA_URL         = os.getenv("OPA_URL", "http://moe-opa:8181")
OPA_ENABLED     = os.getenv("OPA_ENABLED", "true").lower() not in ("0", "false", "no")
OPA_FAIL_OPEN   = os.getenv("OPA_FAIL_OPEN", "false").lower() in ("1", "true", "yes")
OPA_TIMEOUT     = float(os.getenv("OPA_TIMEOUT", "5"))


def _extract_user(headers: dict[str, str]) -> dict[str, Any]:
    """Build an OPA user input document from request headers.

    moe-sovereign sets these headers when it proxies to moe-codex.
    Frontend or CLI clients may also set them directly.
    """
    groups_raw = headers.get("x-codex-groups", "")
    groups = [g.strip() for g in groups_raw.split(",") if g.strip()] if groups_raw else []
    return {
        "id":        headers.get("x-codex-user-id", ""),
        "groups":    groups,
        "clearance": headers.get("x-codex-clearance", "PUBLIC"),
    }


async def evaluate(
    package: str,
    rule: str,
    input_doc: dict[str, Any],
) -> bool:
    """Evaluate an OPA rule and return the boolean result.

    Args:
        package: Dotted package path, e.g. "codex.catalog".
        rule:    Rule name, e.g. "allow".
        input_doc: Arbitrary dict passed as OPA input.

    Returns:
        True if the rule evaluates to a truthy value, False otherwise.
        Falls back to OPA_FAIL_OPEN if OPA is unreachable.
    """
    if not OPA_ENABLED:
        return True

    path = package.replace(".", "/")
    url  = f"{OPA_URL}/v1/data/{path}/{rule}"
    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT) as client:
            resp = await client.post(url, json={"input": input_doc})
            resp.raise_for_status()
            result = resp.json().get("result", False)
            return bool(result)
    except Exception as exc:
        logger.warning("OPA unreachable (%s): %s — fail_open=%s", url, exc, OPA_FAIL_OPEN)
        return OPA_FAIL_OPEN


async def catalog_allow(user: dict, dataset: dict, action: str = "read") -> bool:
    return await evaluate("codex.catalog", "allow", {
        "user": user, "dataset": dataset, "action": action,
    })


async def approval_allow(user: dict, action: str) -> bool:
    return await evaluate("codex.approval", "allow", {
        "user": user, "action": action,
    })


async def marking_allow(user: dict, dataset: dict) -> bool:
    return await evaluate("codex.data_markings", "allow", {
        "user": user, "dataset": dataset,
    })


async def health_check() -> bool:
    """Returns True if OPA is reachable."""
    if not OPA_ENABLED:
        return True
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{OPA_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False
