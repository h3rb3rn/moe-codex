"""Shared mutable application state for moe-codex.

Mirrors the pattern from moe-sovereign/state.py: globals are None at import
time, the lifespan handler in main.py populates them at startup.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

redis_client: Optional["Redis"] = None
sovereign_reachable: bool = False
enterprise_reachable: bool = False
opa_reachable: bool = False
mlflow_reachable: bool = False
