# Best Practices

Practical guidance for deploying MoE Codex in regulated environments. These pages cover the four key decisions every operator faces before going to production.

## Pages

| Page | What you will learn |
|------|---------------------|
| [Use-Case Discovery](use-case-discovery.md) | How to scope an use case, run stakeholder workshops, and choose the right Codex modules |
| [Data Onboarding](data-onboarding.md) | Bundle format, NiFi pipeline patterns, lakeFS branch strategy, and the approval gate flow |
| [Expert Selection](expert-selection.md) | How to map your domain to the 15 moe-sovereign expert categories and configure routing |

## General Principles

**Start with lineage.** Enable Marquez from day one — retrofitting lineage onto existing pipelines is expensive. Every NiFi flow should emit OpenLineage events before any data reaches the catalog.

**Separate raw from approved.** Use lakeFS branches `raw/<source>/<timestamp>` and `approved/<project>/<version>` as your primary data lifecycle. Never query from `raw` in production.

**Compliance first, features second.** Fill in the use-case compliance checklist before writing any pipeline code. Discovering a GDPR Art. 9 requirement after data is already in the graph means a remediation sprint.

**Keep the approval gate narrow.** The approval workflow is a human decision point, not a rubber stamp. If everything goes through approval, nothing gets reviewed properly. Scope approval to: regulated datasets, model inputs for high-risk AI, and any export destined for external publication.
