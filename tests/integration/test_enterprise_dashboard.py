"""Enterprise dashboard template + endpoint surface tests."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parents[2]


def test_enterprise_template_exists():
    body = (_ROOT / "admin_ui" / "templates" / "enterprise.html").read_text()
    assert "enterprise" in body.lower()


def test_main_exposes_codex_status_endpoint():
    src = (_ROOT / "main.py").read_text()
    assert '@app.get("/v1/codex/status")' in src
