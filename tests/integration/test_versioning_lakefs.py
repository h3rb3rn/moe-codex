"""Versioning service smoke tests — pure unit tests on services/versioning.py."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))


def test_enabled_false_when_endpoint_unset(monkeypatch):
    monkeypatch.delenv("LAKEFS_ENDPOINT", raising=False)
    import importlib
    import services.versioning as v
    importlib.reload(v)
    assert v._enabled() is False


def test_enabled_true_when_endpoint_set(monkeypatch):
    monkeypatch.setenv("LAKEFS_ENDPOINT", "http://moe-lakefs:8000")
    import importlib
    import services.versioning as v
    importlib.reload(v)
    assert v._enabled() is True


def test_pending_branch_prefix_constant():
    import services.versioning as v
    assert v.PENDING_BRANCH_PREFIX == "pending/"


def test_archive_to_branch_signature():
    import services.versioning as v
    sig = inspect.signature(v.archive_to_branch)
    assert "bundle" in sig.parameters
    assert "source_tag" in sig.parameters
    assert "metadata" in sig.parameters
