"""ETL pipeline service smoke tests — pure unit tests on services/etl_pipeline.py."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))


def test_submit_enabled_false_when_url_unset(monkeypatch):
    monkeypatch.delenv("NIFI_INGEST_URL", raising=False)
    import importlib
    import services.etl_pipeline as e
    importlib.reload(e)
    assert e._submit_enabled() is False


def test_submit_enabled_true_when_url_set(monkeypatch):
    monkeypatch.setenv("NIFI_INGEST_URL", "http://moe-nifi:8081/listen-bundle")
    import importlib
    import services.etl_pipeline as e
    importlib.reload(e)
    assert e._submit_enabled() is True


def test_summarise_diagnostics_handles_none():
    import services.etl_pipeline as e
    out = e.summarise_diagnostics(None)
    assert isinstance(out, dict)
