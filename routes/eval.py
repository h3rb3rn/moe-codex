"""routes/eval.py — LLM Evaluation endpoints.

GET  /v1/codex/eval/suites            — list available eval suites
POST /v1/codex/eval/run               — run a suite by name
GET  /v1/codex/eval/health            — MLflow reachability
GET  /v1/codex/eval/runs              — list recent MLflow runs
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.eval import (
    run_suite, list_suites, health_check,
    EVALS_DIR, MLFLOW_URL, MLFLOW_ENABLED,
)

router = APIRouter(prefix="/v1/codex/eval")


@router.get("/health")
async def eval_health():
    ok = await health_check()
    return {"mlflow_reachable": ok, "mlflow_enabled": MLFLOW_ENABLED, "mlflow_url": MLFLOW_URL}


@router.get("/suites")
async def eval_suites():
    suites = await list_suites()
    return {"suites": suites, "evals_dir": str(EVALS_DIR)}


@router.post("/run")
async def eval_run(body: dict):
    """Run an eval suite.

    Body: { "suite": "clinical_accuracy.yaml" }
    Or:   { "suite_path": "/app/evals/custom.yaml" }
    """
    suite_name = body.get("suite") or body.get("suite_path")
    if not suite_name:
        return JSONResponse(status_code=400, content={"error": "suite or suite_path required"})

    suite_path = Path(suite_name) if os.path.isabs(str(suite_name)) else EVALS_DIR / suite_name
    if not suite_path.exists():
        return JSONResponse(status_code=404, content={"error": f"Suite not found: {suite_path}"})

    try:
        result = await run_suite(suite_path)
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/runs")
async def eval_runs(limit: int = 20):
    """Return recent MLflow runs across all moe-codex experiments."""
    if not MLFLOW_ENABLED:
        return {"runs": [], "mlflow_enabled": False}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
                json={
                    "filter": "tags.source = 'moe-codex-eval'",
                    "max_results": limit,
                    "order_by": ["start_time DESC"],
                },
            )
            r.raise_for_status()
            runs = r.json().get("runs", [])
            return {
                "runs": [
                    {
                        "run_id":      run["info"]["run_id"],
                        "name":        run["info"].get("run_name", ""),
                        "status":      run["info"].get("status", ""),
                        "start_time":  run["info"].get("start_time"),
                        "metrics":     {m["key"]: m["value"] for m in run.get("data", {}).get("metrics", [])},
                    }
                    for run in runs
                ]
            }
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"MLflow unreachable: {exc}"})
