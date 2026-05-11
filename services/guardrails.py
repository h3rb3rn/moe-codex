"""services/guardrails.py — NeMo Guardrails-compatible config loader & enforcer.

Implements a subset of the NeMo Guardrails Colang 2.0 config format.
Does NOT require the NeMo library — uses pattern matching and optional
moe-sovereign judge calls for LLM-based classification.

Guardrails config directory layout (GUARDRAILS_DIR):
  config.yml          — rail definitions
  prompts.yml         — custom prompt overrides (optional)

config.yml schema:
  rails:
    input:
      flows:
        - block jailbreak
        - block sensitive pii
    output:
      flows:
        - check response relevance
  patterns:
    block jailbreak:
      type: regex
      patterns:
        - "ignore (all )?previous instructions"
        - "pretend you are"
        - "DAN mode"
    block sensitive pii:
      type: regex
      patterns:
        - "\\b\\d{3}-\\d{2}-\\d{4}\\b"   # SSN
        - "\\b[A-Z]{2}\\d{6}\\b"           # Passport-style
    check response relevance:
      type: llm-check
      threshold: 0.7
      prompt: "Rate 0-1: Is this response relevant and appropriate? Response: {output}"
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

GUARDRAILS_DIR    = Path(os.getenv("GUARDRAILS_DIR", "/app/guardrails"))
SOVEREIGN_URL     = os.getenv("SOVEREIGN_URL", "http://moe-sovereign:8002")
SOVEREIGN_API_KEY = os.getenv("SOVEREIGN_API_KEY", "")
GUARDRAILS_ENABLED = os.getenv("GUARDRAILS_ENABLED", "true").lower() not in ("0", "false", "no")
GUARDRAILS_TIMEOUT = float(os.getenv("GUARDRAILS_TIMEOUT", "10"))

_config_cache: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    global _config_cache
    config_file = GUARDRAILS_DIR / "config.yml"
    if not config_file.exists():
        return {}
    try:
        _config_cache = yaml.safe_load(config_file.read_text()) or {}
        return _config_cache
    except Exception as e:
        logger.warning("Failed to load guardrails config: %s", e)
        return {}


def reload_config() -> dict[str, Any]:
    """Force reload of guardrails config from disk."""
    global _config_cache
    _config_cache = None
    return _load_config()


def get_config() -> dict[str, Any]:
    if _config_cache is None:
        return _load_config()
    return _config_cache


# ─── Pattern matching ─────────────────────────────────────────────────────────

def _check_regex_pattern(text: str, pattern_def: dict[str, Any]) -> tuple[bool, str]:
    """Returns (blocked, matched_pattern)."""
    for pat in pattern_def.get("patterns", []):
        if re.search(pat, text, re.IGNORECASE):
            return True, pat
    return False, ""


# ─── LLM check ───────────────────────────────────────────────────────────────

async def _llm_check(text: str, prompt_template: str, threshold: float) -> tuple[bool, float]:
    """Ask moe-sovereign to score the text; block if score < threshold."""
    prompt = prompt_template.replace("{output}", text[:2000]).replace("{input}", text[:2000])
    try:
        async with httpx.AsyncClient(timeout=GUARDRAILS_TIMEOUT) as c:
            headers = {"Content-Type": "application/json"}
            if SOVEREIGN_API_KEY:
                headers["Authorization"] = f"Bearer {SOVEREIGN_API_KEY}"
            r = await c.post(
                f"{SOVEREIGN_URL}/v1/chat/completions",
                json={"model": "general_assistant",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 5},
                headers=headers,
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            # Parse first float in response (e.g. "0.85" or "Score: 0.9")
            match = re.search(r"\d+\.?\d*", raw)
            score = float(match.group()) if match else 0.0
            # Normalize if score > 1 (model returned 0-10 scale)
            if score > 1:
                score = score / 10.0
            return score < threshold, score
    except Exception as exc:
        logger.warning("LLM guardrail check failed: %s — allowing", exc)
        return False, 1.0


# ─── Public API ───────────────────────────────────────────────────────────────

class GuardrailViolation(Exception):
    def __init__(self, flow: str, reason: str):
        self.flow   = flow
        self.reason = reason
        super().__init__(f"Guardrail '{flow}' blocked: {reason}")


async def check_input(text: str) -> list[dict[str, Any]]:
    """Check text against all configured input rails.

    Returns list of violation dicts (empty = all clear).
    """
    if not GUARDRAILS_ENABLED:
        return []
    config   = get_config()
    patterns = config.get("patterns", {})
    input_flows: list[str] = (config.get("rails", {}).get("input", {}).get("flows") or [])
    violations: list[dict] = []

    for flow in input_flows:
        pat_def = patterns.get(flow)
        if not pat_def:
            continue
        ptype = pat_def.get("type", "regex")
        if ptype == "regex":
            blocked, matched = _check_regex_pattern(text, pat_def)
            if blocked:
                violations.append({"flow": flow, "type": "regex", "matched": matched})
        elif ptype == "llm-check":
            prompt_tpl = pat_def.get("prompt", "Is this input safe? {input}")
            threshold  = float(pat_def.get("threshold", 0.5))
            blocked, score = await _llm_check(text, prompt_tpl, threshold)
            if blocked:
                violations.append({"flow": flow, "type": "llm-check", "score": score})

    return violations


async def check_output(text: str) -> list[dict[str, Any]]:
    """Check LLM output against all configured output rails."""
    if not GUARDRAILS_ENABLED:
        return []
    config   = get_config()
    patterns = config.get("patterns", {})
    output_flows: list[str] = (config.get("rails", {}).get("output", {}).get("flows") or [])
    violations: list[dict] = []

    for flow in output_flows:
        pat_def = patterns.get(flow)
        if not pat_def:
            continue
        ptype = pat_def.get("type", "regex")
        if ptype == "regex":
            blocked, matched = _check_regex_pattern(text, pat_def)
            if blocked:
                violations.append({"flow": flow, "type": "regex", "matched": matched})
        elif ptype == "llm-check":
            prompt_tpl = pat_def.get("prompt", "Is this response appropriate? {output}")
            threshold  = float(pat_def.get("threshold", 0.5))
            blocked, score = await _llm_check(text, prompt_tpl, threshold)
            if blocked:
                violations.append({"flow": flow, "type": "llm-check", "score": score})

    return violations
