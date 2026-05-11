"""Phase 20-24 feature surface tests for moe-codex.

Source-scan based: verifies routes, page templates, helper symbols and the
data-health drift classifier are present in the migrated codex codebase.
Topology has shifted vs. moe-sovereign — endpoints now live under /v1/codex/*.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))


# ─── Phase 20: Data Catalog ──────────────────────────────────────────────────

@pytest.mark.parametrize("pattern", [
    r'@router\.get\("/catalog/datasets"',
    r'_marquez_datasets',
    r'_lakefs_repositories',
])
def test_phase20_catalog_endpoints(pattern):
    src = (_ROOT / "routes" / "catalog.py").read_text()
    assert re.search(pattern, src), f"Phase 20 missing in routes/catalog.py: {pattern!r}"


def test_phase20_catalog_template_exists():
    body = (_ROOT / "admin_ui" / "templates" / "catalog.html").read_text()
    for required in ("loadCatalog", "catalog-source-filter"):
        assert required in body


def test_phase20_doc_exists():
    assert (_ROOT / "docs" / "admin" / "catalog.md").exists()


# ─── Phase 21: Approval Workflow ─────────────────────────────────────────────

@pytest.mark.parametrize("pattern", [
    r'@router\.post\("/approval/import/pending"',
    r'@router\.get\("/approval/list"',
    r'@router\.post\("/approval/\{branch:path\}/approve"',
    r'@router\.post\("/approval/\{branch:path\}/reject"',
])
def test_phase21_approval_endpoints(pattern):
    src = (_ROOT / "routes" / "approval.py").read_text()
    assert re.search(pattern, src), f"Phase 21 missing in routes/approval.py: {pattern!r}"


def test_phase21_approval_calls_sovereign_for_import():
    """Codex must delegate Neo4j writes to moe-sovereign — no direct graph_manager calls."""
    src = (_ROOT / "routes" / "approval.py").read_text()
    assert "from services.sovereign_client import knowledge_import" in src
    assert "graph_manager.import_knowledge_bundle" not in src, \
        "codex must not call graph_manager directly — that belongs in moe-sovereign"


def test_phase21_versioning_branch_helpers():
    src = (_ROOT / "services" / "versioning.py").read_text()
    for sym in ("archive_to_branch", "list_pending_branches",
                "get_bundle_from_branch", "approve_branch", "reject_branch",
                "PENDING_BRANCH_PREFIX"):
        assert sym in src, f"versioning.py missing helper: {sym}"


def test_phase21_approval_template_exists():
    body = (_ROOT / "admin_ui" / "templates" / "approval.html").read_text()
    for required in ("approveBranch", "rejectBranch"):
        assert required in body


# ─── Phase 23: Data Health drift detection ───────────────────────────────────

def test_phase23_data_health_module():
    src = (_ROOT / "services" / "data_health.py").read_text()
    for sym in ("def compute_drift(", "async def record_event(",
                "async def recent_events(", "DRIFT_THRESHOLD"):
        assert sym in src


def test_phase23_drift_detection_hook_in_approval():
    src = (_ROOT / "routes" / "approval.py").read_text()
    assert "from services.data_health import compute_drift, record_event" in src


def test_phase23_health_events_endpoint():
    src = (_ROOT / "routes" / "health.py").read_text()
    assert '@router.get("/health/events"' in src


def test_phase23_drift_classification():
    """Pure-function test on compute_drift severity ladder."""
    import importlib
    import services.data_health as dh
    importlib.reload(dh)

    drift = dh.compute_drift(
        {"entities": 100}, {"entities": 109},
        declared_entities=10,
    )
    assert drift["severity"] in ("ok", "info")
    assert drift["delta_entities"] == 9

    drift = dh.compute_drift(
        {"entities": 100}, {"entities": 101},
        declared_entities=10,
    )
    assert drift["severity"] == "warn"
    assert "entity_dedup_suppressed" in drift["flags"]

    drift = dh.compute_drift(
        {"entities": 100}, {"entities": 100},
        declared_entities=10,
    )
    assert drift["severity"] == "crit"
    assert "zero_entities_added" in drift["flags"]

    drift = dh.compute_drift(
        {"entities": 100}, {"entities": 90},
        declared_entities=5,
    )
    assert drift["severity"] == "crit"
    assert "entity_count_shrank" in drift["flags"]


# ─── Phase 22: Object Explorer ───────────────────────────────────────────────
# The Cypher endpoint /v1/graph/cypher/read remains in moe-sovereign (graph
# operation). codex only ships the template.

def test_phase22_explorer_template_exists():
    body = (_ROOT / "admin_ui" / "templates" / "explorer.html").read_text()
    for required in ("runQuery", "cypher-query"):
        assert required in body


# ─── Phase 24: JupyterLite ───────────────────────────────────────────────────

def test_phase24_notebook_template():
    body = (_ROOT / "admin_ui" / "templates" / "notebook.html").read_text()
    for required in ("jupyterlite_url", "snippet-panel", "iframe"):
        assert required in body


def test_phase24_env_documents_jupyterlite_url():
    body = (_ROOT / ".env.example").read_text()
    assert "JUPYTERLITE_URL=" in body


# ─── Cross-cutting: required docs exist ──────────────────────────────────────

@pytest.mark.parametrize("doc", [
    "docs/admin/catalog.md",
    "docs/admin/approval.md",
    "docs/admin/explorer.md",
    "docs/admin/data-health.md",
    "docs/admin/notebook.md",
    "docs/system/palantir_comparison.md",
    "docs/system/license_compliance.md",
])
def test_admin_docs_exist(doc):
    assert (_ROOT / doc).exists(), f"Migration: {doc} missing in moe-codex"


# ─── API contract: codex must expose the right router prefixes ───────────────

def test_main_wires_all_routers():
    src = (_ROOT / "main.py").read_text()
    for router in ("approval", "catalog", "health", "lineage", "versioning", "etl"):
        assert f"from routes.{router}" in src, f"main.py does not import routes.{router}"
        assert f"{router}_router" in src, f"main.py does not include {router}_router"
    assert 'prefix="/v1/codex"' in src, "Routers must be mounted under /v1/codex"
