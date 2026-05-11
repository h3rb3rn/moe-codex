"""MoE Codex service layer.

Public surface for the EU-Palantir-equivalent data platform: lineage,
versioning, ETL fan-out, and data-health drift detection.

Talks to moe-sovereign over HTTP for GraphRAG operations (see api/sovereign_client.py).
"""
