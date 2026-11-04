# Decision 0001: project-local OhMyOrch ingestion adaptation

**Date:** 2026-11-04. **Authority:** explicit user request in this session. **Superseded in part by:** [Decision 0002](0002-ohmyorch-delivery-loop.md), for the plugin install and OpenSpec/continuation exclusions only.

## Requested behavior

The user requested generating Option B's `SPECS.md` from the PRDs, putting the `.claude` coding harness first, and supporting planning, implementation, review and runbook evidence. They specifically requested cloning and adapting `josoroma/OhMyOrch`'s `plugins/ohmyorch/agents/spec-ingestor.md` for this project.

## Project decision

Create a project-local read-only spec-ingestor agent and paired writing skill. Preserve OhMyOrch's source-traceable story backlog, Gherkin acceptance, stable identity, honest statuses, CODEBASE preflight and generated navigation/dependency views. Preserve the existing SP technical decisions in a separate mapped contract. The caller persists the ingestor's proposed specification; ingestion does not implement application code or silently mark delivery complete.

Adapt plugin preflight and paths to `.claude/autobots.json` and local Python scripts. Do not install the upstream plugin, import its unrelated OpenSpec/archive/continuation machinery, or treat its external paths as this project's runtime. Keep independent review and evidence checks from the project's stronger DH-W contract; do not inherit upstream legacy partial-pass completion behavior.

The cloned source is pinned to `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. Record provenance and adaptation differences. Local deterministic validation must check malformed acceptance, missing sources, identity/dependency errors and stale generated navigation. It cannot establish that every sentence is entailed by its source; source review remains necessary.

The product remains Mac-local with local Supabase/Docker and OpenRouter-only inference. This decision authorizes the development-harness adaptation, not a product build, live model qualification, changed developer provider settings or database startup. The staged H0/H1 product prerequisites remain honest about incomplete toolchain/database/adapter qualification.
