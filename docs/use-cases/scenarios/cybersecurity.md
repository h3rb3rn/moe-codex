---
title: Sovereign Threat Intelligence & Security Operations
industry: Cybersecurity & SOC
maturity: beta
ai_act_risk: limited
required_modules:
  - graph_rag
  - mcp_tools
  - codex_catalog
  - codex_lineage
required_experts:
  - security_expert
  - technical_expert
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: personal_data
bsi_modules: [APP.2.1, NET.1.1, NET.3.2, DER.1.1, DER.2.1]
nis2_sector: [digital_infrastructure, ict_service_management]
---

# Sovereign Threat Intelligence & Security Operations

## Problem

SOC teams receive thousands of alerts per day from SIEM, EDR, and threat feeds. Tier-1 analysts spend 80 % of their time on manual triage that could be automated. Threat intelligence enrichment requires correlating CVEs, IOCs, and internal events across tools that don't share a common data model — and existing SaaS SOAR solutions send sensitive log data to US-cloud providers.

MoE Codex provides a sovereign threat intelligence graph: IOCs, CVEs, and alert events are ingested, correlated via GraphRAG, and queryable by analysts in natural language — with full lineage for every enrichment decision, without any data leaving EU infrastructure.

## Compliance Checklist

- [ ] NIS2: incident reporting within 24h/72h — lineage enables evidence packaging
- [ ] BSI DER modules: detection and response toolchain documented
- [ ] GDPR: IP addresses and user identifiers in logs are personal data — pseudonymise before ingest
- [ ] No threat intelligence data to US-cloud SOAR/SIEM platforms
