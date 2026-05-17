"""services/compliance.py — Runtime security and compliance posture (Track D.3.3).

Aggregates signals from two sources:
  1. Falco — runtime threat detection via JSON event log file shared via
     Docker volume (/var/log/falco/events.json). Tails the last N events.
  2. OpenSCAP — compliance scan results stored as JSON in Postgres after
     a scan job completes. Exposes profile pass/fail ratios.

The compliance service intentionally does NOT start scan jobs; it only reads
existing results. Scan scheduling belongs to the operator's CI/CD pipeline
(e.g. a Kestra flow that calls /v1/codex/compliance/scan/trigger).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FALCO_EVENTS_FILE   = os.getenv("FALCO_EVENTS_FILE", "/var/log/falco/events.json")
FALCO_URL           = os.getenv("FALCO_URL", "")          # optional Falco HTTP output
FALCO_MAX_EVENTS    = int(os.getenv("FALCO_MAX_EVENTS", "500"))

OPENSCAP_RESULTS_DIR = os.getenv("OPENSCAP_RESULTS_DIR", "/var/lib/codex/scap")
OPENSCAP_PROFILE     = os.getenv(
    "OPENSCAP_PROFILE",
    "xccdf_org.ssgproject.content_profile_cis_l2",
)

_SEVERITY_ORDER = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "NOTICE": 3,
                   "INFORMATIONAL": 4, "DEBUG": 5}


# ─── Falco ────────────────────────────────────────────────────────────────────

def _parse_falco_line(line: str) -> dict[str, Any] | None:
    try:
        ev = json.loads(line.strip())
        return {
            "time":      ev.get("time", ""),
            "rule":      ev.get("rule", ""),
            "priority":  ev.get("priority", ""),
            "output":    ev.get("output", ""),
            "source":    ev.get("source", "syscall"),
            "hostname":  ev.get("hostname", ""),
            "tags":      ev.get("tags", []),
        }
    except (json.JSONDecodeError, AttributeError):
        return None


def read_falco_events(limit: int = 100) -> list[dict[str, Any]]:
    """Read the most recent Falco events from the shared log file."""
    path = Path(FALCO_EVENTS_FILE)
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.debug("read_falco_events: %s", exc)
        return []

    events: list[dict] = []
    for line in reversed(lines[-FALCO_MAX_EVENTS:]):
        ev = _parse_falco_line(line)
        if ev:
            events.append(ev)
        if len(events) >= limit:
            break
    return events


def falco_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate event counts by priority and top rules."""
    by_priority: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    for ev in events:
        p = ev.get("priority", "UNKNOWN")
        by_priority[p] = by_priority.get(p, 0) + 1
        r = ev.get("rule", "unknown")
        by_rule[r] = by_rule.get(r, 0) + 1

    top_rules = sorted(by_rule.items(), key=lambda x: -x[1])[:10]
    return {
        "total":       len(events),
        "by_priority": by_priority,
        "top_rules":   [{"rule": r, "count": c} for r, c in top_rules],
        "critical":    by_priority.get("CRITICAL", 0),
        "errors":      by_priority.get("ERROR", 0),
    }


async def falco_health() -> bool:
    """Check if Falco is producing events (file exists and is non-empty)."""
    path = Path(FALCO_EVENTS_FILE)
    if path.exists() and path.stat().st_size > 0:
        return True
    if FALCO_URL:
        try:
            async with httpx.AsyncClient(timeout=4) as c:
                r = await c.get(f"{FALCO_URL}/healthz")
                return r.status_code == 200
        except Exception:
            return False
    return False


# ─── OpenSCAP ─────────────────────────────────────────────────────────────────

def _latest_scan_result() -> dict[str, Any] | None:
    """Load the most recent scan result JSON from OPENSCAP_RESULTS_DIR."""
    results_dir = Path(OPENSCAP_RESULTS_DIR)
    if not results_dir.exists():
        return None
    files = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text())
    except Exception as exc:
        logger.debug("_latest_scan_result: %s", exc)
        return None


def get_scan_summary() -> dict[str, Any]:
    """Return compliance posture from the latest OpenSCAP scan."""
    result = _latest_scan_result()
    if not result:
        return {
            "available":  False,
            "profile":    OPENSCAP_PROFILE,
            "scanned_at": None,
            "pass":       0,
            "fail":       0,
            "notchecked": 0,
            "score":      None,
        }

    rules = result.get("rules", [])
    by_result: dict[str, int] = {}
    for rule in rules:
        res = rule.get("result", "notchecked")
        by_result[res] = by_result.get(res, 0) + 1

    passed     = by_result.get("pass", 0)
    failed     = by_result.get("fail", 0)
    total      = passed + failed
    score      = round(passed / total * 100, 1) if total else None
    failed_rules = [
        {"id": r.get("id", ""), "title": r.get("title", "")}
        for r in rules if r.get("result") == "fail"
    ][:20]

    return {
        "available":    True,
        "profile":      result.get("profile", OPENSCAP_PROFILE),
        "scanned_at":   result.get("scanned_at", ""),
        "pass":         passed,
        "fail":         failed,
        "notchecked":   by_result.get("notchecked", 0),
        "score":        score,
        "failed_rules": failed_rules,
    }


def trigger_scan() -> dict[str, Any]:
    """Attempt to run an oscap scan if the binary is available locally.

    This is a best-effort fallback for operators who have openscap-scanner
    installed on the host. Container-based scanning should be triggered via
    a Kestra workflow instead.
    """
    try:
        result = subprocess.run(
            ["oscap", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"status": "unavailable", "message": "oscap binary not found"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "message": "oscap binary not found"}

    results_dir = Path(OPENSCAP_RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp   = int(time.time())
    output_file = results_dir / f"scan_{timestamp}.xml"

    proc = subprocess.Popen(
        [
            "oscap", "xccdf", "eval",
            "--profile", OPENSCAP_PROFILE,
            "--results", str(output_file),
            "/usr/share/xml/scap/ssg/content/ssg-debian12-xccdf.xml",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return {
        "status":  "started",
        "pid":     proc.pid,
        "output":  str(output_file),
        "profile": OPENSCAP_PROFILE,
    }
