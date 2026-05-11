---
title: Financial Risk & Regulatory Reporting Intelligence
industry: Banking & Finance
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
  - financial_advisor
  - legal_advisor
  - data_analyst
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: personal_data
bsi_modules: [APP.2.1, APP.3.1, NET.1.1]
nis2_sector: [banking, financial_market_infrastructure]
---

# Financial Risk & Regulatory Reporting Intelligence

## Problem

Banks face simultaneous regulatory pressures from EBA, ECB, BaFin, and DORA. Risk analysts spend months preparing SREP submissions and stress test reports from fragmented data warehouses. Model explainability requirements (ECB TRIM, SR 11-7) demand full audit trails for every model input and transformation.

MoE Codex provides a lineage-complete, versioned data intelligence platform where every risk model input is catalogued, approved, and traceable from raw source to regulatory output.

## Architecture

```mermaid
flowchart LR
    A[Core Banking / DWH] -->|NiFi ETL| B[lakeFS\nVersioned Risk Data]
    B --> C[Catalog\nModel Registry]
    C --> D[moe-sovereign\nLLM Routing]
    D --> E[Regulatory Report\nExport]
    D -->|Lineage| F[Marquez\nSR 11-7 Audit Trail]
```

## Compliance Checklist

- [ ] DORA Art. 6: ICT risk management framework documented
- [ ] EBA Guidelines on ICT and Security Risk Management
- [ ] ECB TRIM / SR 11-7: full model lineage via Marquez mandatory
- [ ] BaFin BAIT: access logs and four-eyes principle via codex_approval
- [ ] NIS2 banking sector requirements
- [ ] No US-cloud processing of customer financial data (GDPR international transfer restrictions)
