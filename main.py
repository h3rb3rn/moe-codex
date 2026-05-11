"""moe-codex — EU-Palantir-Alternative backend.

Ships the data-platform surface (catalog, approval, lineage, versioning,
ETL, drift detection) as an optional add-on to moe-sovereign. Talks to
moe-sovereign only at clearly defined HTTP boundaries — see
services/sovereign_client.py.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import state
from services.sovereign_client import health_check as sovereign_health

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        from redis.asyncio import from_url as redis_from_url
        state.redis_client = redis_from_url(redis_url, decode_responses=True)
        try:
            await state.redis_client.ping()
            logger.info("Redis/Valkey reachable at %s", redis_url.split("@")[-1])
        except Exception as e:
            logger.warning("Redis/Valkey not reachable: %s", e)
            state.redis_client = None

    state.sovereign_reachable = await sovereign_health()
    logger.info("moe-sovereign reachable: %s", state.sovereign_reachable)

    try:
        from services.lineage import _enabled as lineage_enabled
        from services.versioning import _enabled as versioning_enabled
        state.enterprise_reachable = any([lineage_enabled(), versioning_enabled()])
    except Exception:
        state.enterprise_reachable = False

    yield

    if state.redis_client is not None:
        await state.redis_client.aclose()


app = FastAPI(
    title="MoE Codex",
    version="0.1.0",
    description=(
        "EU-sovereign data and audit platform. Open-source alternative to "
        "Palantir Foundry / Gotham / AIP. Optional add-on to moe-sovereign."
    ),
    lifespan=lifespan,
)


# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    """Lightweight health probe — does not call upstream services."""
    return {
        "status": "ok",
        "service": "moe-codex",
        "version": app.version,
    }


@app.get("/v1/codex/status")
async def codex_status() -> dict:
    """Detailed status — verifies upstream sovereign + enterprise stack reachability."""
    from services.lineage import _enabled as lineage_enabled
    from services.versioning import _enabled as versioning_enabled
    from services.etl_pipeline import _enabled as etl_enabled
    return {
        "service": "moe-codex",
        "sovereign_reachable": await sovereign_health(),
        "lineage_enabled":     lineage_enabled(),
        "versioning_enabled":  versioning_enabled(),
        "etl_enabled":         etl_enabled(),
        "redis_reachable":     state.redis_client is not None,
    }


# ─── Router wiring ──────────────────────────────────────────────────────────

from routes.approval  import router as approval_router
from routes.catalog   import router as catalog_router
from routes.health    import router as health_router
from routes.lineage   import router as lineage_router
from routes.versioning import router as versioning_router
from routes.etl       import router as etl_router

app.include_router(approval_router,   prefix="/v1/codex")
app.include_router(catalog_router,    prefix="/v1/codex")
app.include_router(health_router,     prefix="/v1/codex")
app.include_router(lineage_router,    prefix="/v1/codex")
app.include_router(versioning_router, prefix="/v1/codex")
app.include_router(etl_router,        prefix="/v1/codex")


@app.exception_handler(Exception)
async def generic_handler(request, exc):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc)})
