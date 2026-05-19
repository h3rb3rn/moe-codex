"""services/compliance.py — Runtime security and compliance posture (Track D.3.3).

Two-tier architecture that works on bare metal AND on QEMU/KVM VMs:

Tier 1 — Falco (bare metal / physical hosts):
  Runtime syscall monitoring via eBPF. Requires BPF_MAP_TYPE_RINGBUF in the
  kernel (available when QEMU exposes cpu=host or on bare metal). Reads events
  from the shared JSON log file at FALCO_EVENTS_FILE.

Tier 2 — Trivy (VM-compatible fallback, works everywhere):
  Container-image vulnerability scanning and misconfiguration detection via
  Docker socket. No kernel access required. Runs as an on-demand scan job
  (docker exec aquasec/trivy) rather than a persistent daemon. Results are
  cached as JSON in TRIVY_RESULTS_DIR.

The service auto-detects which tier is available:
  - falco_health() → True  → Tier 1 active
  - falco_health() → False → fall back to Trivy for the /compliance UI
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

TRIVY_IMAGE          = os.getenv("TRIVY_IMAGE", "aquasec/trivy:latest")
TRIVY_RESULTS_DIR    = os.getenv("TRIVY_RESULTS_DIR", "/var/lib/codex/trivy")
TRIVY_SCAN_TARGETS   = os.getenv("TRIVY_SCAN_TARGETS", "").split(",")  # images to scan
DOCKER_SOCKET        = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")

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


# ─── Trivy (VM-compatible scanner, Falco fallback) ────────────────────────────

def trivy_available() -> bool:
    """Check if Docker socket is accessible for running Trivy containers."""
    return Path(DOCKER_SOCKET).exists()


def _latest_trivy_result() -> dict[str, Any] | None:
    results_dir = Path(TRIVY_RESULTS_DIR)
    if not results_dir.exists():
        return None
    files = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text())
    except Exception as exc:
        logger.debug("_latest_trivy_result: %s", exc)
        return None


def trigger_trivy_scan(target: str = "") -> dict[str, Any]:
    """Run Trivy against a container image or filesystem via Docker.

    Uses the Docker socket so no Trivy binary installation is needed.
    Results are written as JSON to TRIVY_RESULTS_DIR.
    Works on ANY host including QEMU/KVM VMs — no kernel access required.
    """
    if not trivy_available():
        return {
            "status":  "unavailable",
            "message": "Docker socket not accessible. Mount /var/run/docker.sock.",
        }

    results_dir = Path(TRIVY_RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp   = int(time.time())
    output_file = results_dir / f"trivy_{timestamp}.json"

    # Default target: scan the codex API image itself
    if not target:
        target = os.getenv("TRIVY_DEFAULT_TARGET", "moe-codex-codex-api")

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{DOCKER_SOCKET}:/var/run/docker.sock:ro",
        TRIVY_IMAGE,
        "image",
        "--format", "json",
        "--output", f"/tmp/trivy_{timestamp}.json",
        "--quiet",
        target,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            # Copy result out of the container by re-running with file output
            # Actually we need to write to the host — use a volume mount instead
            cmd_with_vol = [
                "docker", "run", "--rm",
                "-v", f"{DOCKER_SOCKET}:/var/run/docker.sock:ro",
                "-v", f"{str(results_dir)}:/results",
                TRIVY_IMAGE,
                "image",
                "--format", "json",
                "--output", f"/results/trivy_{timestamp}.json",
                "--quiet",
                target,
            ]
            subprocess.run(cmd_with_vol, capture_output=True, text=True, timeout=120)
            return {
                "status":  "completed",
                "target":  target,
                "output":  str(output_file),
                "scanner": "trivy",
            }
        return {
            "status":  "error",
            "message": result.stderr[:500] or "Trivy scan failed",
            "scanner": "trivy",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "scanner": "trivy"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "scanner": "trivy"}


def get_trivy_summary() -> dict[str, Any]:
    """Return latest Trivy scan summary — CVE counts by severity."""
    result = _latest_trivy_result()
    if not result:
        return {"available": False, "scanner": "trivy"}

    vuln_counts: dict[str, int] = {}
    misconfig_counts: dict[str, int] = {}
    scanned_targets: list[str] = []

    for res in result.get("Results", []):
        scanned_targets.append(res.get("Target", ""))
        for vuln in res.get("Vulnerabilities") or []:
            sev = vuln.get("Severity", "UNKNOWN")
            vuln_counts[sev] = vuln_counts.get(sev, 0) + 1
        for mc in res.get("Misconfigurations") or []:
            sev = mc.get("Severity", "UNKNOWN")
            misconfig_counts[sev] = misconfig_counts.get(sev, 0) + 1

    total_vulns = sum(vuln_counts.values())
    critical    = vuln_counts.get("CRITICAL", 0)
    high        = vuln_counts.get("HIGH", 0)

    return {
        "available":         True,
        "scanner":           "trivy",
        "scanned_at":        result.get("CreatedAt", ""),
        "targets":           scanned_targets[:5],
        "total_vulns":       total_vulns,
        "critical":          critical,
        "high":              high,
        "vulns_by_severity": vuln_counts,
        "misconfigs":        misconfig_counts,
        "score": max(0, 100 - (critical * 10) - (high * 3)),
    }
