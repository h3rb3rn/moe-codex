---
title: Clinical Decision Support & Patient Data Intelligence
industry: Healthcare & Hospital Networks
maturity: beta
ai_act_risk: high
required_modules:
  - graph_rag
  - mcp_tools
  - codex_catalog
  - codex_approval
  - codex_lineage
required_experts:
  - medical_consult
  - legal_advisor
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: special_category
bsi_baustein: [APP.3.1, SYS.1.3, NET.1.1]
nis2_sector: [healthcare]
---

# Clinical Decision Support & Patient Data Intelligence

## Problem

Hospital networks need to query patient cohort data for clinical research and quality assurance without exposing identifiable records to external cloud services. Existing BI tools lack natural-language query capabilities, and every ad-hoc analysis requires manual data extraction by a data engineer.

MoE Codex provides a sovereign CDS layer: pseudonymised patient data is catalogued, lineage-tracked, and queryable via natural language — with mandatory human-in-the-loop approval for any query touching sensitive attributes.

## Architecture

```mermaid
flowchart LR
    A[HIS / EHR Systems] -->|Pseudonymised Export| B[Catalog + lakeFS]
    B --> C[moe-sovereign\nLLM Routing]
    C --> D[Approval Gate\nDPO Review]
    D --> E[Result Report]
```

## Compliance Checklist

- [ ] GDPR Art. 9 (health data): DPO mandatory, DPIA required
- [ ] AI Act Annex III high-risk: human reviewer for all clinical suggestions
- [ ] NIS2 healthcare sector requirements
- [ ] §203 StGB (medical confidentiality): all model access logged via Marquez
- [ ] Pseudonymisation protocol documented and auditable
