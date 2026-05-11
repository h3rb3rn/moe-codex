---
title: Telecom Network & Customer Intelligence
industry: Telecommunications
maturity: beta
ai_act_risk: limited
required_modules:
  - graph_rag
  - mcp_tools
  - codex_catalog
  - codex_lineage
required_experts:
  - technical_expert
  - data_analyst
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: personal_data
bsi_modules: [APP.2.1, NET.1.1, NET.3.2]
nis2_sector: [digital_infrastructure, telecoms]
---

# Telecom Network & Customer Intelligence

## Problem

Telecom operators manage petabytes of network telemetry and subscriber data. Churn prediction, network fault root-cause analysis, and regulatory reporting (BNetzA, BEREC) require correlating multiple systems in near real-time. GDPR and TKG 2021 impose strict processing restrictions on subscriber metadata.

MoE Codex enables telecom-grade data intelligence with strict data segregation: network telemetry (no PII) and subscriber analytics (GDPR-scoped) flow through separate pipelines with independent approval gates and lineage tracks.

## Compliance Checklist

- [ ] GDPR + TKG 2021 §§ 3, 174 ff.: subscriber metadata processing restricted to specific purposes
- [ ] BNetzA data retention ruling: no unlawful retention
- [ ] NIS2 telecommunications sector requirements
- [ ] Strict network/subscriber pipeline segregation in NiFi flows
