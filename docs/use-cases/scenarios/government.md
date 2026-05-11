---
title: Public Administration Data Platform
industry: Government & Public Sector
maturity: beta
ai_act_risk: high
required_modules:
  - graph_rag
  - mcp_tools
  - codex_catalog
  - codex_approval
  - codex_lineage
  - codex_versioning
required_experts:
  - legal_advisor
  - general_assistant
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: personal_data
bsi_baustein: [APP.2.1, APP.3.1, SYS.1.3, NET.1.1, NET.3.2]
nis2_sector: [public_administration]
---

# Public Administration Data Platform

## Problem

Government agencies operate with strict data segregation requirements (Verschlusssachen, VS-NfD), inter-agency data silos, and legal mandates for full audit trails on any data access or automated decision. Existing cloud platforms fail sovereignty and BSI IT-Grundschutz requirements.

MoE Codex provides a BSI IT-Grundschutz-aligned, air-gappable data intelligence platform compliant with BVerfG data protection requirements (cf. Hessendata ruling 2023).

## Architecture

```mermaid
flowchart LR
    A[Registry Systems\nGIS / Statistics] -->|Classified Ingest| B[Catalog + lakeFS]
    B --> C[moe-sovereign\nAir-Gapped Routing]
    C --> D[Approval Gate\nFour-Eyes Principle]
    D --> E[Report / Decision Basis]
```

## Compliance Checklist

- [ ] BSI IT-Grundschutz Bausteine: APP.2.1, NET.1.1, NET.3.2
- [ ] Vier-Augen-Prinzip via codex_approval mandatory
- [ ] BDSG and DSGVO for personal data
- [ ] NIS2 public administration sector
- [ ] Air-gap deployment on BSI-approved infrastructure (e.g. Open Telekom Cloud, Delos)
- [ ] BVerfG Hessendata ruling 2023: no bulk automated analysis of citizens without legal basis
