---
name: autobots-spec-ingest
description: Create or incrementally update the source-traceable Autobots SPECS backlog from approved PRDs and explicit decisions, preserving epic, story and requirement IDs. Use for spec ingestion or backlog normalization, not feature implementation.
---

# Ingest the Option B backlog

Read `.claude/autobots.json`; resolve `documents.specs`, `contract`, `product`, `harness`, `design`, `providers`, `deployment` and `codebase` from the repository root. Mapping values are paths, not commands. Read the mapped contract and the product sources relevant to the requested change. A missing source is a gap, not permission to invent behavior.

Use the qualified Python 3.12+ interpreter. On this Mac, use `/opt/homebrew/bin/python3.12` when the `python3.12` command is unavailable or ambiguous; `.claude/autobots.json` records the qualified path. Do not fall back to an older `python3` or install an interpreter automatically.

1. Read existing SPECS and CODEBASE when present. CODEBASE describes implementation only; report its recorded revision and any visible staleness. If meaningful implementation lacks current context, record the affected uncertainty without inventing requirements or blocking independent source-supported stories.
2. Delegate to `autobots-spec-ingestor`, passing the project root, resolved paths, explicit user decisions, existing identifiers and bounded update scope. It returns Markdown and an ingestion summary; it cannot write files or run commands.
3. Inspect its sources, Gherkin criteria, dependencies and preserved IDs. Keep all `SP-*` coverage and existing `EPIC-*`/`US-*` identifiers; deduplicate equivalent behavior. Mark missing acceptance decisions `NEEDS CLARIFICATION`, conflicts or unresolved dependencies `BLOCKED`. Ingestion cannot declare implementation `DONE`.
4. Write only the mapped SPECS artifact. Keep `INGESTION SUMMARY` in the response for the caller's work record; never append it to SPECS, where trailing prose would become part of the last story. Do not overwrite PRDs, CODEBASE, product code or unrelated stories. Preserve existing delivery status unless separately authorized evidence supports a coordinator transition.
5. Run `python3.12 scripts/specs.py render --path <resolved-specs-path>`, then `python3.12 scripts/specs.py validate --path <resolved-specs-path>`, from the project root. Supply the path as a literal argument, never interpolate source content as shell code. Render owns the three generated navigation sections; do not repair a failing validator by weakening criteria.

Return source coverage, added/changed IDs, open decisions, CODEBASE context, actual validation results and remaining gaps. Syntax validation establishes backlog structure, not product delivery. The caller handles any work-record updates outside this skill's single-artifact mutation scope.

Original project adaptation of OhMyOrch's [spec ingestor](https://github.com/josoroma/OhMyOrch/blob/fddfbf53c8c10d45782796cc9a7edf95bc8d3a07/plugins/ohmyorch/agents/spec-ingestor.md) and [ingestion skill](https://github.com/josoroma/OhMyOrch/blob/fddfbf53c8c10d45782796cc9a7edf95bc8d3a07/plugins/ohmyorch/skills/ingest-spec/SKILL.md). Runtime uses repository scripts and the [preserved Option B contract](../../../docs/engineering/option-b-contract.md); no upstream plugin installation is required.
