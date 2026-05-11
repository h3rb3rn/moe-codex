---
title: Insurance Risk Assessment & Regulatory Intelligence
industry: Insurance
maturity: experimental
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
gdpr_relevance: special_category
bsi_modules: [APP.2.1, APP.3.1]
nis2_sector: [financial_market_infrastructure]
---

# Insurance Risk Assessment & Regulatory Intelligence

## Problem

Insurers are subject to Solvency II, BaFin VAG, and GDPR simultaneously. Actuarial models require explainability for BaFin examinations, and claims processing touching health data (§ Art. 9 GDPR) requires special-category safeguards. Existing platforms lack the lineage depth needed for model auditability.

MoE Codex provides a lineage-complete actuarial intelligence platform with mandatory human-in-the-loop approval for high-value claims decisions and full model explainability trails for BaFin.

## Compliance Checklist

- [ ] Solvency II: model documentation and validation trail via Marquez
- [ ] BaFin VAG: underwriting model explainability for regulatory examinations
- [ ] GDPR Art. 22: automated decision-making in underwriting requires human review — codex_approval mandatory
- [ ] GDPR Art. 9: health data in claims processing requires explicit legal basis
- [ ] AI Act Annex III high-risk: conformity assessment for insurance scoring models
