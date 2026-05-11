---
title: Crisis Response & Emergency Coordination
industry: Civil Protection & Crisis Management
maturity: beta
ai_act_risk: high
required_modules:
  - graph_rag
  - mcp_tools
  - codex_catalog
  - codex_lineage
required_experts:
  - general_assistant
  - technical_expert
recommended_models:
  planner: ""
  judge: ""
gdpr_relevance: personal_data
bsi_modules: [APP.2.1, NET.1.1, SYS.1.3]
nis2_sector: [public_administration]
---

# Crisis Response & Emergency Coordination

## Problem

Crisis management agencies (THW, Feuerwehr, BBK — Federal Office of Civil Protection) coordinate across dozens of organisations with incompatible data formats and no shared situational awareness layer. Real-time querying of resource availability, affected populations, and infrastructure status requires minutes of manual lookup that could be seconds.

MoE Codex provides a sovereign real-time coordination intelligence layer, deployable on mobile infrastructure, with NiFi ingesting feeds from disparate agencies and GraphRAG enabling natural-language situational queries.

## Compliance Checklist

- [ ] NIS2 public administration: redundancy and continuity requirements
- [ ] GDPR for affected-population data: access limited to authorised responders
- [ ] AI Act: high-risk category for emergency management systems
- [ ] Offline/deployable mode: moe-sovereign must run without internet (air-gap capable)
- [ ] Data retention: incident data must be archived for post-incident review
