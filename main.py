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

    from services.opa import health_check as opa_health
    state.opa_reachable = await opa_health()
    logger.info("OPA reachable: %s", state.opa_reachable)

    from services.eval import health_check as mlflow_health
    state.mlflow_reachable = await mlflow_health()
    logger.info("MLflow reachable: %s", state.mlflow_reachable)

    from services.guardrails import reload_config as gr_reload
    _gr = gr_reload()
    logger.info("Guardrails loaded: %d patterns", len(_gr.get("patterns", {})))

    from services.trino import health_check as trino_health
    state.trino_reachable = await trino_health()
    logger.info("Trino reachable: %s", state.trino_reachable)

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
    from services.etl_pipeline import _submit_enabled as etl_enabled
    from services.opa import health_check as opa_health, OPA_ENABLED
    from services.eval import MLFLOW_ENABLED
    from services.guardrails import get_config, GUARDRAILS_ENABLED
    from services.trino import TRINO_ENABLED
    gr_config = get_config()
    return {
        "service": "moe-codex",
        "sovereign_reachable": await sovereign_health(),
        "lineage_enabled":     lineage_enabled(),
        "versioning_enabled":  versioning_enabled(),
        "etl_enabled":         etl_enabled(),
        "redis_reachable":     state.redis_client is not None,
        "opa_enabled":         OPA_ENABLED,
        "opa_reachable":       state.opa_reachable,
        "mlflow_enabled":      MLFLOW_ENABLED,
        "mlflow_reachable":    state.mlflow_reachable,
        "guardrails_enabled":  GUARDRAILS_ENABLED,
        "guardrails_patterns": len(gr_config.get("patterns", {})),
        "trino_enabled":       TRINO_ENABLED,
        "trino_reachable":     state.trino_reachable,
    }


# ─── Router wiring ──────────────────────────────────────────────────────────

from routes.approval   import router as approval_router
from routes.catalog    import router as catalog_router
from routes.health     import router as health_router
from routes.lineage    import router as lineage_router
from routes.versioning import router as versioning_router
from routes.etl        import router as etl_router
from routes.opa        import router as opa_router
from routes.eval       import router as eval_router
from routes.guardrails import router as guardrails_router
from routes.trino      import router as trino_router

app.include_router(approval_router,   prefix="/v1/codex")
app.include_router(catalog_router,    prefix="/v1/codex")
app.include_router(health_router,     prefix="/v1/codex")
app.include_router(lineage_router,    prefix="/v1/codex")
app.include_router(versioning_router, prefix="/v1/codex")
app.include_router(etl_router,        prefix="/v1/codex")
app.include_router(opa_router)
app.include_router(eval_router)
app.include_router(guardrails_router)
app.include_router(trino_router)


@app.exception_handler(Exception)
async def generic_handler(request, exc):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc)})
