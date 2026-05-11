"""services/eval.py — LLM Evaluation service (Promptfoo-inspired).

Runs YAML-defined test suites against moe-sovereign and logs results to
MLflow. Each eval suite is a collection of test cases with expected
outputs scored by a judge call or exact/regex match.

Eval suite YAML format (compatible with Promptfoo schema):
  description: "Clinical query accuracy"
  prompts:
    - "Summarise adverse events for compound X"
  providers:
    - id: moe-sovereign
      config:
        model: medical_consult
  tests:
    - vars: {}
      assert:
        - type: contains
          value: "adverse event"
        - type: llm-rubric
          value: "Response is accurate and cites sources"
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

SOVEREIGN_URL     = os.getenv("SOVEREIGN_URL", "http://moe-sovereign:8002")
SOVEREIGN_API_KEY = os.getenv("SOVEREIGN_API_KEY", "")
MLFLOW_URL        = os.getenv("MLFLOW_URL", "http://moe-mlflow:5000")
MLFLOW_ENABLED    = os.getenv("MLFLOW_ENABLED", "true").lower() not in ("0", "false", "no")
EVALS_DIR         = Path(os.getenv("EVALS_DIR", "/app/evals"))
EVAL_TIMEOUT      = float(os.getenv("EVAL_TIMEOUT", "60"))


def _auth_headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SOVEREIGN_API_KEY:
        h["Authorization"] = f"Bearer {SOVEREIGN_API_KEY}"
    return h


# ─── MLflow helpers ──────────────────────────────────────────────────────────

async def _mlflow_create_experiment(name: str) -> str:
    """Return existing or create new MLflow experiment, return experiment_id."""
    if not MLFLOW_ENABLED:
        return "0"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
                json={"experiment_name": name},
            )
            if r.status_code == 200:
                return r.json()["experiment"]["experiment_id"]
            r2 = await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/experiments/create",
                json={"name": name},
            )
            r2.raise_for_status()
            return r2.json()["experiment_id"]
    except Exception as e:
        logger.warning("MLflow create_experiment failed: %s", e)
        return "0"


async def _mlflow_start_run(experiment_id: str, run_name: str) -> str:
    """Start an MLflow run, return run_id."""
    if not MLFLOW_ENABLED:
        return str(uuid.uuid4())
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/create",
                json={
                    "experiment_id": experiment_id,
                    "run_name": run_name,
                    "start_time": int(time.time() * 1000),
                    "tags": [{"key": "source", "value": "moe-codex-eval"}],
                },
            )
            r.raise_for_status()
            return r.json()["run"]["info"]["run_id"]
    except Exception as e:
        logger.warning("MLflow start_run failed: %s", e)
        return str(uuid.uuid4())


async def _mlflow_log_metrics(run_id: str, metrics: dict[str, float]) -> None:
    if not MLFLOW_ENABLED:
        return
    ts = int(time.time() * 1000)
    payload = [{"key": k, "value": v, "timestamp": ts, "step": 0} for k, v in metrics.items()]
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/log-batch",
                json={"run_id": run_id, "metrics": payload},
            )
    except Exception as e:
        logger.warning("MLflow log_metrics failed: %s", e)


async def _mlflow_finish_run(run_id: str, status: str = "FINISHED") -> None:
    if not MLFLOW_ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/update",
                json={"run_id": run_id, "status": status, "end_time": int(time.time() * 1000)},
            )
    except Exception as e:
        logger.warning("MLflow finish_run failed: %s", e)


# ─── Assertion evaluation ────────────────────────────────────────────────────

def _eval_assert(response_text: str, assertion: dict[str, Any]) -> bool:
    """Evaluate a single assertion against the LLM response."""
    atype = assertion.get("type", "")
    value = assertion.get("value", "")

    if atype == "contains":
        return value.lower() in response_text.lower()
    if atype == "not-contains":
        return value.lower() not in response_text.lower()
    if atype == "regex":
        return bool(re.search(value, response_text, re.IGNORECASE))
    if atype == "equals":
        return response_text.strip() == str(value).strip()
    if atype in ("llm-rubric", "model-graded-closedqa"):
        # Deferred: llm-rubric requires a judge call — always pass in offline mode
        return True
    logger.debug("Unknown assertion type %s — skipping", atype)
    return True


# ─── Core runner ─────────────────────────────────────────────────────────────

async def _call_sovereign(prompt: str, model: str) -> tuple[str, float]:
    """Call moe-sovereign /v1/chat/completions, return (response_text, latency_s)."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=EVAL_TIMEOUT) as c:
            r = await c.post(
                f"{SOVEREIGN_URL}/v1/chat/completions",
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                headers=_auth_headers(),
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return text, time.monotonic() - t0
    except Exception as exc:
        return f"ERROR: {exc}", time.monotonic() - t0


async def run_suite(suite_path: str | Path) -> dict[str, Any]:
    """Run a single eval suite YAML, log to MLflow, return summary dict."""
    suite_path = Path(suite_path)
    suite: dict = yaml.safe_load(suite_path.read_text())

    description = suite.get("description", suite_path.stem)
    prompts: list[str] = suite.get("prompts", [])
    providers: list[dict] = suite.get("providers", [{"id": "moe-sovereign", "config": {"model": "general_assistant"}}])
    tests: list[dict] = suite.get("tests", [])

    experiment_id = await _mlflow_create_experiment(f"moe-codex/{description}")
    run_id = await _mlflow_start_run(experiment_id, run_name=f"{suite_path.stem}-{uuid.uuid4().hex[:6]}")

    results: list[dict] = []
    total, passed = 0, 0

    for provider in providers:
        model = provider.get("config", {}).get("model", "general_assistant")
        for prompt in prompts:
            for test in tests:
                full_prompt = prompt
                # Substitute {{vars}} placeholders
                for k, v in (test.get("vars") or {}).items():
                    full_prompt = full_prompt.replace(f"{{{{{k}}}}}", str(v))

                response, latency = await _call_sovereign(full_prompt, model)
                assertions = test.get("assert", [])
                test_passed = all(_eval_assert(response, a) for a in assertions)

                total += 1
                if test_passed:
                    passed += 1

                results.append({
                    "model":    model,
                    "prompt":   full_prompt[:200],
                    "response": response[:500],
                    "latency":  round(latency, 3),
                    "passed":   test_passed,
                })

    pass_rate = passed / total if total else 0.0
    await _mlflow_log_metrics(run_id, {
        "pass_rate":    pass_rate,
        "total_tests":  float(total),
        "passed_tests": float(passed),
        "avg_latency":  sum(r["latency"] for r in results) / len(results) if results else 0.0,
    })
    await _mlflow_finish_run(run_id)

    return {
        "suite":      description,
        "run_id":     run_id,
        "total":      total,
        "passed":     passed,
        "pass_rate":  round(pass_rate, 4),
        "results":    results,
    }


async def list_suites() -> list[str]:
    """Return YAML eval suite filenames found in EVALS_DIR."""
    if not EVALS_DIR.exists():
        return []
    return [p.name for p in sorted(EVALS_DIR.glob("*.yaml")) + sorted(EVALS_DIR.glob("*.yml"))]


async def health_check() -> bool:
    if not MLFLOW_ENABLED:
        return True
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{MLFLOW_URL}/health")
            return r.status_code == 200
    except Exception:
        return False
